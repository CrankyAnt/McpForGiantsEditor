-- Research-only bridge for controlled scene-fidelity observations.
-- The launcher supplies absolute MCP_PROBE_ROOT, MCP_EXPECTED_SCENE and
-- MCP_EXPECTED_TARGET values. It may set MCP_MUTATE_TRANSLATION=true once.
local base = assert(MCP_PROBE_ROOT, "missing_probe_root")
local expectedScene = assert(MCP_EXPECTED_SCENE, "missing_expected_scene")
local expectedTarget = assert(MCP_EXPECTED_TARGET, "missing_expected_target")

local requestId = 1
local saveId = 0
local initialized = false
local mutationApplied = false
local targetRoot = nil
local readyFile = MCP_READY_FILE or "ready.xml"
local sampleFile = MCP_SAMPLE_FILE or "samples.xml"
assert(type(readyFile) == "string" and not string.find(readyFile, "[\\/]") and readyFile ~= "", "invalid_ready_file")
assert(type(sampleFile) == "string" and not string.find(sampleFile, "[\\/]") and sampleFile ~= "", "invalid_sample_file")

local function normalized(path)
    return string.lower(string.gsub(path or "", "\\", "/"))
end

local function numberString(value)
    return string.format("%.17g", value)
end

local function setValues(xml, prefix, values)
    for key, value in pairs(values) do
        if type(value) == "number" then value = numberString(value) end
        setXMLString(xml, prefix .. "." .. key, tostring(value))
    end
end

local function writeResponse(filename, result)
    local xml = createXMLFile("mcpFidelity", base .. filename, "probe")
    setValues(xml, "probe", result)
    saveXMLFile(xml)
    delete(xml)
end

local function finite(value)
    return value ~= nil and value == value and value ~= math.huge and value ~= -math.huge
end

local function hasFunctions(names)
    for _, name in ipairs(names) do
        if type(_G[name]) ~= "function" then return nil, "binding_unavailable:" .. name end
    end
    return true
end

local function requireScene()
    local ok, reason = hasFunctions({
        "getRootNode", "getSceneFilename", "getNumOfChildren", "getChildAt",
        "getName", "getTranslation", "getQuaternion", "getRotation", "getScale"
    })
    if not ok then return nil, reason end
    if normalized(getSceneFilename()) ~= normalized(expectedScene) then
        return nil, "unexpected_scene"
    end
    return true
end

local function localPose(node)
    local x, y, z = getTranslation(node)
    local qx, qy, qz, qw = getQuaternion(node)
    local rx, ry, rz = getRotation(node)
    local sx, sy, sz = getScale(node)
    return {
        x = x, y = y, z = z, qx = qx, qy = qy, qz = qz, qw = qw,
        rx = rx, ry = ry, rz = rz, sx = sx, sy = sy, sz = sz
    }
end

local function writePose(xml, prefix, pose)
    for key, value in pairs(pose) do setXMLString(xml, prefix .. "#" .. key, numberString(value)) end
end

local function collectScene()
    local ok, reason = requireScene()
    if not ok then return nil, reason end

    local root = getRootNode()
    local candidate = getChildAt(root, 0)
    if candidate == nil or candidate == 0 then return nil, "scene_root_child_missing" end
    if getName(candidate) ~= expectedTarget then return nil, "unexpected_target_root" end

    local materialReady = hasFunctions({ "getHasClassId", "getNumOfMaterials", "getMaterial", "getMaterialAlbedoColor" })
        and type(ClassIds) == "table" and ClassIds.SHAPE ~= nil
    local animationReady = hasFunctions({
        "getAnimCharacterSet", "getAnimNumOfClips", "getAnimClipName", "getAnimClipDuration"
    })
    local scene = { root = root, target = candidate, nodes = {}, characterSets = {}, characterSetList = {}, incomplete = "" }
    if not materialReady then scene.incomplete = "material_bindings_unavailable" end
    if not animationReady then
        scene.incomplete = scene.incomplete == "" and "animation_bindings_unavailable"
            or scene.incomplete .. ";animation_bindings_unavailable"
    end

    local pending = { { node = root, path = "" } }
    local cursor = 1
    while cursor <= #pending do
        if #scene.nodes >= 10000 then return nil, "node_cap_exceeded" end
        local item = pending[cursor]
        cursor = cursor + 1
        local record = {
            node = item.node, path = item.path, name = getName(item.node), pose = localPose(item.node),
            isShape = false, materials = {}
        }
        if materialReady and getHasClassId(item.node, ClassIds.SHAPE) then
            record.isShape = true
            local count = getNumOfMaterials(item.node)
            for slot = 0, count - 1 do
                local material = getMaterial(item.node, slot)
                local success, r, g, b, a = getMaterialAlbedoColor(material)
                record.materials[#record.materials + 1] = {
                    slot = slot, success = success == true, r = r, g = g, b = b, a = a
                }
            end
        end
        if animationReady then
            local characterSet = getAnimCharacterSet(item.node)
            if characterSet ~= nil and characterSet ~= 0 then
                local key = tostring(characterSet)
                if scene.characterSets[key] == nil then
                    local set = { handle = characterSet, nodePath = item.path, clips = {} }
                    local count = getAnimNumOfClips(characterSet)
                    for clip = 0, count - 1 do
                        set.clips[#set.clips + 1] = {
                            index = clip, name = getAnimClipName(characterSet, clip),
                            duration = getAnimClipDuration(characterSet, clip)
                        }
                    end
                    scene.characterSets[key] = set
                    scene.characterSetList[#scene.characterSetList + 1] = set
                end
            end
        end
        scene.nodes[#scene.nodes + 1] = record
        local childCount = getNumOfChildren(item.node)
        for childIndex = 0, childCount - 1 do
            pending[#pending + 1] = {
                node = getChildAt(item.node, childIndex), path = item.path .. "/" .. childIndex
            }
        end
    end
    return scene
end

local function sceneStats(scene)
    local shapeCount, materialCount, clipCount, setCount = 0, 0, 0, 0
    for _, node in ipairs(scene.nodes) do
        if node.isShape then shapeCount = shapeCount + 1 end
        materialCount = materialCount + #node.materials
    end
    for _, set in ipairs(scene.characterSetList) do
        setCount = setCount + 1
        clipCount = clipCount + #set.clips
    end
    return {
        scene = getSceneFilename(), targetName = getName(scene.target), nodeCount = #scene.nodes,
        shapeCount = shapeCount, materialSlotCount = materialCount, characterSetCount = setCount,
        animationClipCount = clipCount, incomplete = scene.incomplete
    }
end

local function writeScene(xml, prefix, scene)
    for index, node in ipairs(scene.nodes) do
        local key = string.format("%s.node(%d)", prefix, index - 1)
        setXMLString(xml, key .. "#path", node.path)
        setXMLString(xml, key .. "#name", node.name or "")
        setXMLBool(xml, key .. "#shape", node.isShape)
        writePose(xml, key, node.pose)
        for materialIndex, material in ipairs(node.materials) do
            local materialKey = string.format("%s.material(%d)", key, materialIndex - 1)
            setXMLInt(xml, materialKey .. "#slot", material.slot)
            setXMLBool(xml, materialKey .. "#success", material.success)
            if material.r ~= nil then setXMLString(xml, materialKey .. "#r", numberString(material.r)) end
            if material.g ~= nil then setXMLString(xml, materialKey .. "#g", numberString(material.g)) end
            if material.b ~= nil then setXMLString(xml, materialKey .. "#b", numberString(material.b)) end
            if material.a ~= nil then setXMLString(xml, materialKey .. "#a", numberString(material.a)) end
        end
    end
    local setIndex = 0
    for _, set in ipairs(scene.characterSetList) do
        local key = string.format("%s.characterSet(%d)", prefix, setIndex)
        setXMLString(xml, key .. "#nodePath", set.nodePath)
        for clipIndex, clip in ipairs(set.clips) do
            local clipKey = string.format("%s.clip(%d)", key, clipIndex - 1)
            setXMLInt(xml, clipKey .. "#index", clip.index)
            setXMLString(xml, clipKey .. "#name", clip.name or "")
            setXMLString(xml, clipKey .. "#duration", numberString(clip.duration))
        end
        setIndex = setIndex + 1
    end
end

local function writeSceneReceipt(filename, result, scene)
    local xml = createXMLFile("mcpFidelity", base .. filename, "probe")
    setValues(xml, "probe", result)
    writeScene(xml, "probe", scene)
    saveXMLFile(xml)
    delete(xml)
end

local function restorePoses(scene)
    for _, node in ipairs(scene.nodes) do
        local pose = node.pose
        setTranslation(node.node, pose.x, pose.y, pose.z)
        setRotation(node.node, pose.rx, pose.ry, pose.rz)
        setScale(node.node, pose.sx, pose.sy, pose.sz)
    end
end

local function movingCount(scene)
    local count = 0
    for _, node in ipairs(scene.nodes) do
        local current = localPose(node.node)
        local initial = node.pose
        if current.x ~= initial.x or current.y ~= initial.y or current.z ~= initial.z
            or current.qx ~= initial.qx or current.qy ~= initial.qy or current.qz ~= initial.qz or current.qw ~= initial.qw
            or current.rx ~= initial.rx or current.ry ~= initial.ry or current.rz ~= initial.rz
            or current.sx ~= initial.sx or current.sy ~= initial.sy or current.sz ~= initial.sz then
            count = count + 1
        end
    end
    return count
end

local function writeFrame(xml, prefix, scene, characterSet, clip, fraction)
    local duration = clip.duration
    local time = duration * fraction
    setAnimTrackTime(characterSet.handle, 0, time, true)
    local trackTime = getAnimTrackTime(characterSet.handle, 0)
    setXMLString(xml, prefix .. "#requestedTime", numberString(time))
    setXMLString(xml, prefix .. "#trackTime", numberString(trackTime))
    setXMLInt(xml, prefix .. "#movingNodeCount", movingCount(scene))
    for index, node in ipairs(scene.nodes) do
        local key = string.format("%s.node(%d)", prefix, index - 1)
        setXMLString(xml, key .. "#path", node.path)
        setXMLString(xml, key .. "#name", node.name or "")
        writePose(xml, key, localPose(node.node))
    end
end

local function configureTrack(characterSet, clip)
    assignAnimTrackClip(characterSet.handle, 0, clip.index)
    enableAnimTrack(characterSet.handle, 0)
    setAnimTrackSpeedScale(characterSet.handle, 0, 0)
    setAnimTrackLoopState(characterSet.handle, 0, false)
    setAnimTrackBlendWeight(characterSet.handle, 0, 1)
end

local function requireAnimationControl()
    return hasFunctions({
        "assignAnimTrackClip", "enableAnimTrack", "disableAnimTrack", "setAnimTrackSpeedScale",
        "setAnimTrackLoopState", "setAnimTrackBlendWeight", "setAnimTrackTime", "getAnimTrackTime",
        "setTranslation", "setRotation", "setScale", "refreshViewport"
    })
end

local function sample(scene)
    local ok, reason = requireAnimationControl()
    if not ok then return nil, reason end
    local xml = createXMLFile("mcpFidelitySample", base .. sampleFile, "sample")
    local cleanups = {}
    local success, failure = xpcall(function()
        local setIndex = 0
        for _, characterSet in ipairs(scene.characterSetList) do
            for _, clip in ipairs(characterSet.clips) do
                if not finite(clip.duration) or clip.duration < 0 then error("invalid_clip_duration") end
                configureTrack(characterSet, clip)
                cleanups[#cleanups + 1] = characterSet
                local clipKey = string.format("sample.characterSet(%d).clip(%d)", setIndex, clip.index)
                setXMLString(xml, clipKey .. "#nodePath", characterSet.nodePath)
                setXMLString(xml, clipKey .. "#name", clip.name or "")
                setXMLString(xml, clipKey .. "#duration", numberString(clip.duration))
                for step = 0, 40 do
                    writeFrame(xml, string.format("%s.frame(%d)", clipKey, step), scene, characterSet, clip, step / 40)
                end
            end
            setIndex = setIndex + 1
        end
    end, function(message) return tostring(message) end)
    -- Sampling does not restore track assignment, loop state or speed state. It disables
    -- track 0 and restores local poses. The caller must not save after this command.
    for _, characterSet in ipairs(cleanups) do disableAnimTrack(characterSet.handle, 0) end
    restorePoses(scene)
    saveXMLFile(xml)
    delete(xml)
    if not success then return nil, "sample_error:" .. failure end
    return true
end

local function seekPose(scene, xml)
    local clipName = getXMLString(xml, "request#clipName") or ""
    local fraction = tonumber(getXMLString(xml, "request#fraction"))
    if clipName == "" then return nil, "missing_clip_name" end
    if not finite(fraction) or fraction < 0 or fraction > 1 then return nil, "invalid_fraction" end
    local matches = {}
    for _, characterSet in ipairs(scene.characterSetList) do
        for _, clip in ipairs(characterSet.clips) do
            if clip.name == clipName then matches[#matches + 1] = { characterSet = characterSet, clip = clip } end
        end
    end
    if #matches ~= 1 then return nil, "clip_name_not_unique" end
    local ok, reason = requireAnimationControl()
    if not ok then return nil, reason end
    local match = matches[1]
    configureTrack(match.characterSet, match.clip)
    setAnimTrackTime(match.characterSet.handle, 0, match.clip.duration * fraction, true)
    refreshViewport()
    return {
        clipName = match.clip.name, fraction = fraction,
        requestedTime = match.clip.duration * fraction,
        trackTime = getAnimTrackTime(match.characterSet.handle, 0),
        movingNodeCount = movingCount(scene)
    }
end

local function frameView(scene)
    local ok, reason = hasFunctions({
        "getCamera", "getWorldTranslation", "setWorldTranslation", "setWorldDirection", "refreshViewport"
    })
    if not ok then return nil, reason end
    local camera = getCamera()
    if camera == nil or camera == 0 then return nil, "active_camera_missing" end
    local x, y, z = getWorldTranslation(scene.target)
    local cameraX, cameraY, cameraZ = x + 14, y + 8, z + 14
    setWorldTranslation(camera, cameraX, cameraY, cameraZ)
    setWorldDirection(camera, cameraX - x, cameraY - (y + 2), cameraZ - z, 0, 1, 0)
    refreshViewport()
    return { cameraX = cameraX, cameraY = cameraY, cameraZ = cameraZ, targetX = x, targetY = y + 2, targetZ = z }
end

local function render(xml)
    local filename = getXMLString(xml, "request#filename") or ""
    if not string.match(filename, "^[%w_-]+%.png$") then return nil, "invalid_render_filename" end
    local path = base .. filename
    if fileExists(path) then return nil, "render_file_exists" end
    local ok, reason = hasFunctions({ "renderScreenshot" })
    if not ok then return nil, reason end
    -- Exact bundled call shape from scripts/camera/saveBillboards.lua. This remains
    -- unvalidated for general asset rendering.
    renderScreenshot(path, 512, 512, 1, "raw_alpha", 0, 0, 0, 0, 0, 3, 12, false)
    return { receiptPath = filename, renderCandidate = "unvalidated" }
end

local function initialize()
    if initialized then return true end
    local scene, reason = collectScene()
    if not scene then
        writeResponse(readyFile, { ok = false, error = reason })
        return nil, reason
    end
    targetRoot = scene.target
    if MCP_MUTATE_TRANSLATION == true or MCP_MUTATE_TRANSLATION == "true" or MCP_MUTATE_TRANSLATION == "1" then
        local ok, mutationReason = hasFunctions({ "setTranslation" })
        if not ok then
            writeResponse(readyFile, { ok = false, error = mutationReason })
            return nil, mutationReason
        end
        if not mutationApplied then
            setTranslation(targetRoot, 7.25, -1.5, 2.125)
            mutationApplied = true
            scene, reason = collectScene()
            if not scene then
                writeResponse(readyFile, { ok = false, error = reason })
                return nil, reason
            end
        end
    end
    initialized = true
    local result = sceneStats(scene)
    result.ok = true
    result.error = ""
    result.op = "ready"
    result.requestId = 0
    writeSceneReceipt(readyFile, result, scene)
    print("MCP_FIDELITY_READY")
    return true
end

local function command(op, xml)
    local scene, reason = collectScene()
    if not scene then return { ok = false, error = reason, op = op } end
    local result = sceneStats(scene)
    result.ok = true
    result.op = op
    result.error = ""
    if op == "inspect" then
        writeSceneReceipt("inspect.xml", result, scene)
        result.receipt = "inspect.xml"
    elseif op == "sample" then
        local sampled, sampleReason = sample(scene)
        if not sampled then return { ok = false, error = sampleReason, op = op } end
        result.sampleFile = sampleFile
    elseif op == "pose" then
        local pose, poseReason = seekPose(scene, xml)
        if not pose then return { ok = false, error = poseReason, op = op } end
        for key, value in pairs(pose) do result[key] = value end
    elseif op == "view" then
        local view, viewReason = frameView(scene)
        if not view then return { ok = false, error = viewReason, op = op } end
        for key, value in pairs(view) do result[key] = value end
    elseif op == "render" then
        local rendered, renderReason = render(xml)
        if not rendered then return { ok = false, error = renderReason, op = op } end
        for key, value in pairs(rendered) do result[key] = value end
    elseif op == "quit" then
        local canExit, exitReason = hasFunctions({ "editorExit" })
        if not canExit then return { ok = false, error = exitReason, op = op } end
        result.status = "closing"
    else
        return { ok = false, error = "unsupported_operation", op = op }
    end
    return result
end

function MCP_FIDELITY_SCENE_DISPATCH()
    local ok = initialize()
    if not ok then return end
    local path = base .. string.format("request-%03d.xml", requestId)
    if not fileExists(path) then return end
    local xml = loadXMLFile("request", path)
    local op = ""
    local result
    if xml == nil or xml == 0 then
        result = { ok = false, error = "request_xml_unreadable" }
    else
        op = getXMLString(xml, "request#op") or ""
        local called, value = xpcall(function() return command(op, xml) end, function(message) return tostring(message) end)
        if called then result = value else result = { ok = false, error = "command_error:" .. value, op = op } end
        delete(xml)
    end
    result.requestId = requestId
    result.op = result.op or op
    result.error = result.error or ""
    writeResponse(string.format("response-%03d.xml", requestId), result)
    requestId = requestId + 1
    if op == "quit" and result.ok then editorExit(0) end
end

MCP_NATIVE_DISPATCH = MCP_FIDELITY_SCENE_DISPATCH

addEventListener(HookType.ON_FILE_OPEN, initialize)
addEventListener(HookType.ON_SAVE, function(filepath)
    if not initialized then return end
    local called, scene, reason = pcall(collectScene)
    if not called then
        reason = "save_snapshot_error:" .. tostring(scene)
        scene = nil
    end
    saveId = saveId + 1
    if not scene then
        writeResponse(string.format("save-%03d.xml", saveId), {
            ok = false, error = reason, op = "save", requestId = saveId, path = filepath
        })
        return
    end
    local result = sceneStats(scene)
    result.ok = true
    result.error = ""
    result.op = "save"
    result.requestId = saveId
    result.path = filepath
    writeSceneReceipt(string.format("save-%03d.xml", saveId), result, scene)
end)

initialize()
