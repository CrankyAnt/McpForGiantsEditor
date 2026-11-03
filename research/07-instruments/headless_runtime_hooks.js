// Research hooks for the pinned Editor in an owned private-desktop process.
// The Python launcher defines PROBE_MODE before loading this script.
const hooks = new Set();
const callbacks = [];
const forcedBackends={'force-d3d12':0,'force-gnm':1,'force-ps5':2,'force-nvn':3,'force-metal':4,'force-null':6,'force-null-tracking':7};
let app = null;
function text(p, wide) {
    try { if (p.isNull()) return null; if (p.toUInt32() < 65536) return '#' + p.toUInt32(); return wide ? p.readUtf16String() : p.readCString(); }
    catch (_) { return '<unreadable>'; }
}
function where(p) {
    const m = Process.findModuleByAddress(p);
    return m ? m.name + '+' + p.sub(m.base) : p.toString();
}
function emit(event) { event.thread = Process.getCurrentThreadId(); send(event); }
function attach(module, name, spec) {
    const address = module.findExportByName(name);
    if (address === null || hooks.has(name)) return;
    hooks.add(name);
    Interceptor.attach(address, spec);
    emit({event:'hook_installed', name:name});
}
function observe(module) {
    if(/^(kernel32|kernelbase)\.dll$/i.test(module.name))attach(module,'WriteFile',{
        onEnter(args) {try {const value=args[1].readUtf8String(Math.min(args[2].toUInt32(),1024));if(value.includes('Unable to create canvas for '))emit({event:'canvas_error_write',message:value.trim()});}catch(_){} }
    });
    if (/^(editor\.exe|vulkan-1\.dll|d3d12\.dll|dxgi\.dll|opengl32\.dll)$/i.test(module.name)) emit({event:'module_loaded',name:module.name});
    if (module.name.toLowerCase() === 'editor.exe') {
        Interceptor.attach(module.base.add(0x1d8670), {
            onEnter(args) { this.config=args[0]; },
            onLeave(ret) {
                const before=this.config.add(0x2b0).readU32();
                if(Object.prototype.hasOwnProperty.call(forcedBackends,PROBE_MODE))this.config.add(0x2b0).writeU32(forcedBackends[PROBE_MODE]);
                emit({event:'renderer_config_constructed',before:before,after:this.config.add(0x2b0).readU32()});
            }
        });
        Interceptor.attach(module.base.add(0x304330), {
            onEnter(args) { emit({event:'renderer_factory_enter',enum:args[2].add(0x2b0).readU32()}); },
            onLeave(ret) { emit({event:'renderer_factory_leave',result:ret.toString()}); }
        });
        for (const rva of [0x14e1f0, 0x15c440]) {
            Interceptor.attach(module.base.add(rva), {
                onEnter(args) { if(rva===0x15c440)app=args[0];emit({event:'editor_function_enter', rva:'0x'+rva.toString(16)}); },
                onLeave(ret) { emit({event:'editor_function_leave', rva:'0x'+rva.toString(16)}); }
            });
        }
    }
    if (module.name.toLowerCase() === 'win32u.dll') {
        const address = module.findExportByName('NtUserCreateWindowEx');
        if (address !== null && !hooks.has('NtUserCreateWindowEx')) {
            hooks.add('NtUserCreateWindowEx');
            if (PROBE_MODE === 'deny-windows') {
                const callback = new NativeCallback(function () {
                    emit({event:'window_creation_denied', api:'NtUserCreateWindowEx'});
                    return ptr(0);
                }, 'pointer', []);
                callbacks.push(callback);
                Interceptor.replace(address, callback);
            } else {
                Interceptor.attach(address, {
                    onEnter() { this.caller=where(this.returnAddress); },
                    onLeave(ret) { emit({event:'native_window_created', hwnd:ret.toString(), caller:this.caller}); }
                });
            }
            emit({event:'hook_installed', name:'NtUserCreateWindowEx'});
        }
    }
    if (module.name.toLowerCase() !== 'user32.dll') return;
    for (const name of ['CreateWindowExW','CreateWindowExA']) {
        if(PROBE_MODE === 'deny-editor-frame') {
            const address=module.findExportByName(name);
            const types=['uint32','pointer','pointer','uint32','int','int','int','int','pointer','pointer','pointer','pointer'];
            const original=new NativeFunction(address,'pointer',types);
            const replacement=new NativeCallback(function(ex,cls,title,style,x,y,w,h,parent,menu,inst,param) {
                const className=text(cls,name.endsWith('W'));
                if(parent.isNull() && className==='wxWindowNR' && (style & 0x40000000)===0) {
                    emit({event:'editor_frame_creation_denied',api:name,class:className,title:text(title,name.endsWith('W'))});
                    return ptr(0);
                }
                const result=original(ex,cls,title,style,x,y,w,h,parent,menu,inst,param);
                emit({event:'create_window',api:name,class:className,title:text(title,name.endsWith('W')),style:style,parent:parent.toString(),hwnd:result.toString()});
                return result;
            },'pointer',types);
            callbacks.push(replacement);
            Interceptor.replace(address,replacement);
            emit({event:'hook_installed',name:name});
            continue;
        }
        attach(module,name,{
            onEnter(args) {
                this.record={event:'create_window',api:name,class:text(args[1],name.endsWith('W')),title:text(args[2],name.endsWith('W')),style:args[3].toUInt32(),parent:args[8].toString(),caller:where(this.returnAddress)};
                if(app!==null) { try {this.record.app_renderer_enum=app.add(0x690).readPointer().add(0x2b0).readU32();}catch(_){} }
                if (PROBE_MODE === 'force-hidden') {
                    args[3]=ptr(args[3].toUInt32() & ~0x10000000);
                    args[0]=ptr(args[0].toUInt32() | 0x08000000);
                }
            },
            onLeave(ret) { this.record.hwnd=ret.toString();emit(this.record); }
        });
    }
    for (const name of ['ShowWindow','ShowWindowAsync']) {
        attach(module,name,{
            onEnter(args) {
                emit({event:'show_window',api:name,hwnd:args[0].toString(),requested:args[1].toInt32(),caller:where(this.returnAddress)});
                if(PROBE_MODE === 'force-hidden')args[1]=ptr(0);
            }
        });
    }
    attach(module,'SetWindowPos',{
        onEnter(args) {
            if(PROBE_MODE === 'force-hidden')args[6]=ptr((args[6].toUInt32() & ~0x0040) | 0x0080 | 0x0010);
        }
    });
    for (const name of ['MessageBoxW','MessageBoxA']) {
        attach(module,name,{onEnter(args) {emit({event:'message_box',api:name,message:text(args[1],name.endsWith('W')),caption:text(args[2],name.endsWith('W'))});}});
    }
}
Process.attachModuleObserver({onAdded:observe});
Interceptor.flush();
emit({event:'instrumentation_ready',mode:PROBE_MODE,version:Frida.version});
