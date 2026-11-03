-- Research bridge for an owned scene on a private Win32 desktop.
local base = assert(PROBE_ROOT)
local expectedScene = assert(PROBE_EXPECTED_SCENE)
local expectedTarget = assert(PROBE_EXPECTED_TARGET)
local initialized, target, saveSequence, heartbeatSequence = false, nil, 0, 0
local updateCalls = 0
local lastHeartbeatTime = 0
local function normalized(value) return string.lower(string.gsub(value or "", "\\", "/")) end
local function write(filename, values)
    local xml = createXMLFile("desktopResearch", base .. filename, "probe")
    for key, value in pairs(values) do setXMLString(xml, "probe." .. key, tostring(value)) end
    saveXMLFile(xml)
    delete(xml)
end
local function snapshot()
    local x,y,z=getTranslation(target)
    return {ok=true,scene=getSceneFilename(),target=getName(target),x=x,y=y,z=z,heartbeat=heartbeatSequence,updateCalls=updateCalls}
end
local function initialize()
    if initialized or normalized(getSceneFilename()) ~= normalized(expectedScene) then return end
    local root=getRootNode()
    for index=0,getNumOfChildren(root)-1 do
        local child=getChildAt(root,index)
        if getName(child)==expectedTarget then target=child;break end
    end
    assert(target~=nil,"expected_target_missing")
    initialized=true
    local result=snapshot();result.op="ready"
    write("ready.xml",result)
end
local function dispatch()
    assert(initialized,"scene_not_ready")
    local xml=loadXMLFile("desktopRequest",base.."request.xml")
    assert(xml~=nil and xml~=0,"request_unreadable")
    local sequence=getXMLInt(xml,"request#seq")
    local op=getXMLString(xml,"request#op")
    local result=snapshot()
    if op=="mutate" then
        setTranslation(target,sequence*0.001,-1.5,2.125)
        result=snapshot()
    elseif op=="render" then
        local camera=getCamera()
        local x,y,z=getWorldTranslation(target)
        setWorldTranslation(camera,x+6,y+4,z+6)
        setWorldDirection(camera,6,3,6,0,1,0)
        refreshViewport()
        renderScreenshot(base..string.format("view-%06d.png",sequence),512,512,1,"raw_alpha",0,0,0,0,0,3,12,false)
    elseif op=="uncaught-error" then
        delete(xml)
        error("desktop_research_uncaught_error")
    elseif op=="lua-error" then
        local ok,message=pcall(function() error("desktop_research_controlled_error") end)
        result.errorCaught=not ok
        result.error=tostring(message)
    elseif op=="missing-asset" then
        local ok,node=pcall(loadI3DFile,base.."intentionally-missing.i3d")
        result.callReturned=ok
        result.loadedNode=tostring(node)
        if ok and type(node)=="number" and node~=0 then delete(node) end
    elseif op=="gc" then
        result.luaKBBefore=collectgarbage("count")
        collectgarbage("collect")
        result.luaKBAfter=collectgarbage("count")
    elseif op=="update-start" then
        startUpdateLoop()
    elseif op=="update-stop" then
        stopUpdateLoop()
    elseif op=="inspect" then
        -- Read-only scene receipt.
    elseif op=="quit" then
        result.op=op;result.seq=sequence
        write(string.format("response-%06d.xml",sequence),result)
        result.op="done"
        write("done.xml",result)
        delete(xml)
        editorExit(0)
        return
    else error("unsupported_research_operation:"..tostring(op)) end
    result.op=op;result.seq=sequence
    write(string.format("response-%06d.xml",sequence),result)
    delete(xml)
end
MCP_NATIVE_DISPATCH=dispatch
addEventListener(HookType.ON_FILE_OPEN,initialize)
addEventListener(HookType.ON_SAVE,function(path)
    if not initialized then return end
    saveSequence=saveSequence+1
    local result=snapshot();result.path=path;result.op="save";result.seq=saveSequence
    write(string.format("save-%06d.xml",saveSequence),result)
end)
addUpdateListener("desktopResearchHeartbeat",nil,function(_,dt)
    updateCalls=updateCalls+1
    if not initialized then initialize();return end
    local now=getTime()
    if now-lastHeartbeatTime>=5 then
        lastHeartbeatTime=now;heartbeatSequence=heartbeatSequence+1
        write("heartbeat.xml",snapshot())
    end
end)
initialize()
