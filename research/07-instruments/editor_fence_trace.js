// Observer for the pinned Editor 10.0.14 x64 build. The host verifies its hash.
// Hooks record calls; they never replace results, close target handles or submit GPU work.
// Use with trace_editor_fences.py for an owned private-desktop case, at most 60 seconds.
if (Process.arch !== "x64") throw Error("requires pinned x64 build");
const ed = Process.getModuleByName("editor.exe"),
  nt = Process.getModuleByName("ntdll.dll");
const createPtr = ed.base.add(0x27037d0).readPointer();
if (Instruction.parse(ed.base.add(0x43e708)).mnemonic !== "call")
  throw Error("caller instruction mismatch");
const loader = Process.getModuleByName("vulkan-1.dll");
const getProc = new NativeFunction(
  loader.getExportByName("vkGetDeviceProcAddr"),
  "pointer",
  ["pointer", "pointer"],
);
let apiChecked = false,
  metadata = { create_module: Process.findModuleByAddress(createPtr).name },
  serial = 0,
  creates = [],
  destroys = [],
  events = [],
  active = new Map(),
  fences = new Map(),
  calls = [],
  hooked = new Set(),
  openEvents = new Map(),
  truncated = false,
  records = 0;
function append(list, item) {
  if (records >= 100000) {
    truncated = true;
    return;
  }
  records++;
  list.push(item);
}
function frame(a) {
  const m = Process.findModuleByAddress(a);
  return m ? m.name + "+0x" + a.sub(m.base).toString(16) : "unmapped";
}
function hookDestroy(device) {
  const cp = getProc(device, Memory.allocUtf8String("vkCreateFence")),
    dp = getProc(device, Memory.allocUtf8String("vkDestroyFence"));
  metadata.create_pointer_equals_named_lookup = cp.equals(createPtr);
  metadata.destroy_module = Process.findModuleByAddress(dp).name;
  metadata.driver_path = Process.getModuleByName("nvoglv64.dll").path;
  if (!metadata.create_pointer_equals_named_lookup)
    throw Error("named Vulkan pointer mismatch");
  Interceptor.attach(dp, {
    onEnter(args) {
      let h = args[1].toString();
      append(destroys, { fence: h });
      let item = fences.get(h);
      if (item) item.destroy_called = true;
    },
  });
  for (const name of [
    "vkAcquireNextImageKHR",
    "vkQueuePresentKHR",
    "vkQueueSubmit",
    "vkQueueSubmit2",
    "vkQueueSubmit2KHR",
    "vkWaitForFences",
    "vkGetFenceStatus",
    "vkResetFences",
  ]) {
    const address = getProc(device, Memory.allocUtf8String(name));
    if (address.isNull() || hooked.has(address.toString())) continue;
    hooked.add(address.toString());
    Interceptor.attach(address, {
      onEnter(args) {
        this.item = { api: name };
        if (name === "vkAcquireNextImageKHR") {
          this.item.fence = args[4].toString();
          this.item.timeout = args[2].toString();
        } else if (
          name === "vkQueueSubmit" ||
          name === "vkQueueSubmit2" ||
          name === "vkQueueSubmit2KHR"
        ) {
          this.item.fence = args[3].toString();
        } else if (name === "vkGetFenceStatus") {
          this.item.fence = args[1].toString();
        } else if (name === "vkQueuePresentKHR") {
          this.item.chain = [];
          let node = args[1].add(8).readPointer();
          for (let n = 0; n < 8 && !node.isNull(); n++) {
            let st = node.readU32();
            let item = { stype: st };
            if (st === 1000275001) {
              item.fences = [];
              let count = node.add(16).readU32(),
                f = node.add(24).readPointer();
              for (let i = 0; i < Math.min(count, 16); i++)
                item.fences.push(
                  f
                    .add(i * 8)
                    .readPointer()
                    .toString(),
                );
            }
            this.item.chain.push(item);
            node = node.add(8).readPointer();
          }
        } else if (name === "vkWaitForFences" || name === "vkResetFences") {
          const count = args[1].toInt32();
          this.item.fences = [];
          for (let i = 0; i < Math.min(Math.max(count, 0), 64); i++)
            this.item.fences.push(
              args[2]
                .add(i * 8)
                .readPointer()
                .toString(),
            );
        }
      },
      onLeave(ret) {
        this.item.result = ret.toInt32();
        append(calls, this.item);
      },
    });
  }
  apiChecked = true;
}
Interceptor.attach(createPtr, {
  onEnter(args) {
    if (!apiChecked) hookDestroy(args[0]);
    this.id = ++serial;
    this.tid = Process.getCurrentThreadId();
    this.out = args[3];
    this.item = {
      id: this.id,
      stype: args[1].readU32(),
      destroy_called: false,
      stack: Thread.backtrace(this.context, Backtracer.ACCURATE).map(frame),
    };
    active.set(this.tid, this.id);
  },
  onLeave(ret) {
    this.item.result = ret.toInt32();
    if (ret.toInt32() === 0) {
      this.item.fence = this.out.readPointer().toString();
      fences.set(this.item.fence, this.item);
    }
    append(creates, this.item);
    active.delete(this.tid);
  },
});
Interceptor.attach(nt.getExportByName("NtCreateEvent"), {
  onEnter(args) {
    this.out = args[0];
    this.parent = active.get(Process.getCurrentThreadId()) || null;
  },
  onLeave(ret) {
    if (ret.toInt32() === 0) {
      const item = {
        handle: this.out.readPointer().toString(),
        fence_call: this.parent,
        closed: false,
      };
      if (records < 100000) {
        append(events, item);
        openEvents.set(item.handle, item);
      } else truncated = true;
    }
  },
});
Interceptor.attach(nt.getExportByName("NtClose"), {
  onEnter(args) {
    this.h = args[0].toString();
  },
  onLeave(ret) {
    if (ret.toInt32() === 0) {
      const item = openEvents.get(this.h);
      if (item) {
        item.closed = true;
        openEvents.delete(this.h);
      }
    }
  },
});
rpc.exports = {
  summary() {
    return { metadata, creates, destroys, events, calls, truncated };
  },
};
