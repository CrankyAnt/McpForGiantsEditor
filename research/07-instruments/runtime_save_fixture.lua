-- Disposable native-save probe. The launcher sets MCP_PROBE_ROOT.
local base=assert(MCP_PROBE_ROOT)
local id=1
local lastPoll=0
local initialized=false
local saves=0
local node=nil
local function output(filename,values)
    local xml=createXMLFile("mcpProbe",base..filename,"probe")
    for key,value in pairs(values) do setXMLString(xml,"probe."..key,tostring(value)) end
    saveXMLFile(xml);delete(xml)
end
local function readState()
    local x,y,z=getTranslation(node)
    return {scene=getSceneFilename(),node=node,name=getName(node),x=x,y=y,z=z,playing=getIsUpdateLoopPlaying()}
end
local function initialize()
    if initialized then return end
    local scene=getSceneFilename() or ""
    if not string.find(scene,"native-save-fixture.i3d",1,true) then return end
    node=getChild(getRootNode(),"MCP_Save_Probe")
    if node==0 then error("fixture_node_missing") end
    initialized=true
    output("ready.xml",readState())
    print("MCP_NATIVE_READY")
end
addEventListener(HookType.ON_FILE_OPEN,initialize)
addEventListener(HookType.ON_SAVE,function(filepath)
    saves=saves+1
    local state=readState();state.callbackPath=filepath;state.saveNumber=saves
    output(string.format("save-%03d.xml",saves),state)
    print("MCP_NATIVE_SAVED_"..saves)
end)
local function command(op,xml)
    if op=="set" then
        setTranslation(node,getXMLFloat(xml,"request#x"),getXMLFloat(xml,"request#y"),getXMLFloat(xml,"request#z"))
        refreshPanels();refreshViewport()
        return readState()
    elseif op=="inspect" then return readState()
    elseif op=="quit" then return {status="closing"}
    elseif op=="inventory" then
        local inventory=createXMLFile("inventory",base.."inventory.xml","inventory")
        local index=0
        for key,value in next,_G do
            if type(key)=="string" and index<4096 then
                local path=string.format("inventory.global(%d)",index)
                setXMLString(inventory,path.."#name",key)
                setXMLString(inventory,path.."#type",type(value))
                if type(value)=="table" then
                    local mi=0
                    for mk,mv in next,value do
                        if type(mk)=="string" and type(mv)=="function" and mi<512 then
                            setXMLString(inventory,path..string.format(".method(%d)#name",mi),mk);mi=mi+1
                        end
                    end
                end
                index=index+1
            end
        end
        saveXMLFile(inventory);delete(inventory)
        return {globals=index}
    else error("unsupported_operation:"..op) end
end
local function dispatch()
    initialize()
    if not initialized then return end
    local path=base..string.format("request-%03d.xml",id)
    if not fileExists(path) then return end
    local xml=loadXMLFile("request",path);local op=getXMLString(xml,"request#op") or ""
    local ok,result=pcall(command,op,xml);delete(xml)
    if not ok then result={error=tostring(result)} end
    result.ok=ok;result.op=op;output(string.format("response-%03d.xml",id),result)
    print("MCP_NATIVE_RESPONSE_"..id);id=id+1
    if op=="quit" then stopUpdateLoop();editorExit(0) end
end
MCP_NATIVE_DISPATCH=dispatch
local function update(_,dt)
    local now=getTime();if now-lastPoll<1 then return end;lastPoll=now
    dispatch()
end
simulatePhysics(false)
addUpdateListener("mcpNativeSaveUpdate",nil,update)
initialize();startUpdateLoop()