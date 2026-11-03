-- Research-only native dispatch bridge for a copied FS25 vehicle or animated asset.
-- The launcher must provide MCP_PROBE_ROOT (absolute directory ending in slash)
-- and MCP_EXPECTED_SCENE (absolute copied I3D path).
local base=assert(MCP_PROBE_ROOT,"missing_probe_root")
local expected=assert(MCP_EXPECTED_SCENE,"missing_expected_scene")
local expectedTarget=assert(MCP_EXPECTED_TARGET,"missing_expected_target")
local requestId=1
local saveId=0
local initialized=false
local targetRoot=nil

local function normalized(path)
    return string.lower(string.gsub(path or "","\\","/"))
end

local function writeValues(xml,prefix,values)
    for key,value in pairs(values) do setXMLString(xml,prefix.."."..key,tostring(value)) end
end

local function writeResponse(filename,result,snapshot)
    local xml=createXMLFile("mcpProbe",base..filename,"probe")
    writeValues(xml,"probe",result)
    if snapshot then
        for i,node in ipairs(snapshot.nodes) do
            local key=string.format("probe.node(%d)",i-1)
            setXMLString(xml,key.."#path",node.path)
            setXMLString(xml,key.."#name",node.name)
            setXMLFloat(xml,key.."#x",node.x);setXMLFloat(xml,key.."#y",node.y);setXMLFloat(xml,key.."#z",node.z)
            setXMLBool(xml,key.."#shape",node.shape)
            setXMLInt(xml,key.."#materials",node.materials)
            setXMLInt(xml,key.."#vertices",node.vertices)
            setXMLString(xml,key.."#vertexDigestA",tostring(node.vertexDigestA))
            setXMLString(xml,key.."#vertexDigestB",tostring(node.vertexDigestB))
        end
        for i,clip in ipairs(snapshot.clips) do
            local key=string.format("probe.clip(%d)",i-1)
            setXMLString(xml,key.."#nodePath",clip.nodePath)
            setXMLString(xml,key.."#name",clip.name)
            setXMLFloat(xml,key.."#duration",clip.duration)
        end
    end
    saveXMLFile(xml);delete(xml)
end

local function requiredFunctionsPresent()
    return type(getRootNode)=="function" and type(getSceneFilename)=="function"
        and type(getNumOfChildren)=="function" and type(getChildAt)=="function"
        and type(getName)=="function" and type(getTranslation)=="function"
        and type(setTranslation)=="function"
end

local function checkExpectedScene()
    return normalized(getSceneFilename())==normalized(expected)
end

local function requireInspectable()
    if not requiredFunctionsPresent() then return nil,"core_binding_unavailable" end
    if not checkExpectedScene() then return nil,"unexpected_scene" end
    return true
end

local function finite(value)
    return value~=nil and value==value and value~=math.huge and value~=-math.huge
end

local function collectSnapshot()
    local ok,reason=requireInspectable()
    if not ok then return nil,reason end
    local canClassify=type(getHasClassId)=="function" and type(ClassIds)=="table" and ClassIds.SHAPE~=nil
    local canMaterials=canClassify and type(getNumOfMaterials)=="function" and type(getMaterial)=="function"
    local canAnimations=type(getAnimCharacterSet)=="function" and type(getAnimNumOfClips)=="function"
        and type(getAnimClipName)=="function" and type(getAnimClipDuration)=="function"
    local snapshot={nodes={},clips={},shapeCount=0,materialCount=0,incomplete=""}
    if not canClassify then snapshot.incomplete="shape_classification_unavailable" end
    if canClassify and not canMaterials then snapshot.incomplete="material_bindings_unavailable" end
    local root=getRootNode()
    local pending={{node=root,path=""}}
    local cursor=1
    while cursor<=#pending do
        if #snapshot.nodes>=10000 then return nil,"node_cap_exceeded" end
        local item=pending[cursor];cursor=cursor+1
        local x,y,z=getTranslation(item.node)
        local isShape=false
        local materialCount=0
        local vertices=0
        local digestA,digestB=1,1
        if canClassify then
            isShape=getHasClassId(item.node,ClassIds.SHAPE)
            if isShape then
                snapshot.shapeCount=snapshot.shapeCount+1
                if type(getShapeVertexPositions)~="function" then return nil,"vertex_binding_unavailable" end
                local positions
                vertices,positions=getShapeVertexPositions(item.node)
                if vertices==nil or positions==nil then return nil,"vertex_inspection_failed" end
                for vi=1,vertices*3 do
                    local quantized=math.floor(positions[vi]*1000000+0.5)
                    digestA=(digestA*131+quantized)%2147483647
                    digestB=(digestB*137+quantized)%2147483629
                end
                if canMaterials then
                    materialCount=getNumOfMaterials(item.node)
                    snapshot.materialCount=snapshot.materialCount+materialCount
                    for materialIndex=0,materialCount-1 do getMaterial(item.node,materialIndex) end
                end
            end
        end
        snapshot.nodes[#snapshot.nodes+1]={path=item.path,name=getName(item.node),x=x,y=y,z=z,shape=isShape,materials=materialCount,vertices=vertices,vertexDigestA=digestA,vertexDigestB=digestB}
        if canAnimations then
            local characterSet=getAnimCharacterSet(item.node)
            if characterSet and characterSet~=0 then
                local clipCount=getAnimNumOfClips(characterSet)
                for clipIndex=0,clipCount-1 do
                    snapshot.clips[#snapshot.clips+1]={nodePath=item.path,name=getAnimClipName(characterSet,clipIndex),duration=getAnimClipDuration(characterSet,clipIndex)}
                end
            end
        end
        local childCount=getNumOfChildren(item.node)
        for childIndex=0,childCount-1 do
            local child=getChildAt(item.node,childIndex)
            pending[#pending+1]={node=child,path=item.path.."/"..childIndex}
        end
    end
    if not canAnimations then
        snapshot.incomplete=snapshot.incomplete=="" and "animation_bindings_unavailable" or snapshot.incomplete..";animation_bindings_unavailable"
    end
    targetRoot=getChildAt(root,0)
    if targetRoot==nil or targetRoot==0 then return nil,"scene_root_child_missing" end
    if getName(targetRoot)~=expectedTarget then return nil,"unexpected_target_root" end
    return snapshot
end

local function safeSnapshot()
    local ok,snapshot,reason=pcall(collectSnapshot)
    if not ok then return nil,"snapshot_error:"..tostring(snapshot) end
    return snapshot,reason
end

local function resultWithStats(snapshot)
    local x,y,z=getTranslation(targetRoot)
    return {scene=getSceneFilename(),targetName=getName(targetRoot),targetX=x,targetY=y,targetZ=z,
        nodeCount=#snapshot.nodes,shapeCount=snapshot.shapeCount,materialCount=snapshot.materialCount,
        animationClipCount=#snapshot.clips,incomplete=snapshot.incomplete}
end

local function initialize()
    if initialized then return end
    local snapshot,reason=safeSnapshot()
    if not snapshot then
        writeResponse("ready.xml",{ok=false,error=reason,scene=type(getSceneFilename)=="function" and getSceneFilename() or ""})
        return
    end
    initialized=true
    local result=resultWithStats(snapshot);result.ok=true
    writeResponse("ready.xml",result,snapshot)
    print("MCP_PRACTICAL_READY")
    if MCP_READBACK_ONLY==true or MCP_READBACK_ONLY=="true" or MCP_READBACK_ONLY=="1" then
        writeResponse("fresh-readback.xml",result,snapshot)
        editorExit(0)
    end
end

local function command(op,xml)
    local snapshot,reason=safeSnapshot()
    if not snapshot then return {ok=false,error=reason},nil end
    local result=resultWithStats(snapshot);result.ok=true;result.op=op
    if op=="inspect" then return result,snapshot end
    if op=="set" then
        local x=tonumber(getXMLString(xml,"request#x"));local y=tonumber(getXMLString(xml,"request#y"));local z=tonumber(getXMLString(xml,"request#z"))
        if not(finite(x) and finite(y) and finite(z)) then return {ok=false,error="invalid_translation",op=op},snapshot end
        setTranslation(targetRoot,x,y,z)
        snapshot,reason=safeSnapshot()
        if not snapshot then return {ok=false,error=reason,op=op},nil end
        result=resultWithStats(snapshot);result.ok=true;result.op=op
        result.expectedX=x;result.expectedY=y;result.expectedZ=z
        return result,snapshot
    end
    if op=="quit" then result.status="closing";return result,snapshot end
    return {ok=false,error="unsupported_operation",op=op},snapshot
end

function MCP_PRACTICAL_SCENE_DISPATCH()
    initialize()
    if not initialized then return end
    local path=base..string.format("request-%03d.xml",requestId)
    if not fileExists(path) then return end
    local xml=loadXMLFile("request",path)
    local op=""
    local result,snapshot
    if xml==nil or xml==0 then result={ok=false,error="request_xml_unreadable"}
    else
        op=getXMLString(xml,"request#op") or ""
        local ok,value,details=pcall(command,op,xml)
        if ok then result=value;snapshot=details
        else result={ok=false,error="command_error:"..tostring(value),op=op} end
        delete(xml)
    end
    result.requestId=requestId
    writeResponse(string.format("response-%03d.xml",requestId),result,snapshot)
    requestId=requestId+1
    if op=="quit" and result.ok then editorExit(0) end
end

MCP_NATIVE_DISPATCH=MCP_PRACTICAL_SCENE_DISPATCH

addEventListener(HookType.ON_FILE_OPEN,initialize)
addEventListener(HookType.ON_SAVE,function(filepath)
    if not initialized then return end
    local snapshot,reason=safeSnapshot()
    saveId=saveId+1
    if not snapshot then writeResponse(string.format("save-%03d.xml",saveId),{ok=false,error=reason,callbackPath=filepath})
    else local result=resultWithStats(snapshot);result.ok=true;result.callbackPath=filepath;writeResponse(string.format("save-%03d.xml",saveId),result,snapshot) end
end)
initialize()
