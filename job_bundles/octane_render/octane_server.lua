-- Prepares an Octane scene and serves render requests.

local FRAME_NUMBER_PADDING = 4

local SRGB = {
    type = octane.outputColorSpaceType.KNOWN_COLOR_SPACE,
    colorSpace = octane.namedColorSpace.SRGB,
}
local LINEAR_SRGB = {
    type = octane.outputColorSpaceType.KNOWN_COLOR_SPACE,
    colorSpace = octane.namedColorSpace.LINEAR_SRGB,
}

local IMAGE_FORMATS = {
    PNG8   = { format = octane.imageSaveFormat.PNG_8,   extension = "png",
               colorSpace = SRGB },
    PNG16  = { format = octane.imageSaveFormat.PNG_16,  extension = "png",
               colorSpace = SRGB },
    TIFF8  = { format = octane.imageSaveFormat.TIFF_8,  extension = "tif",
               colorSpace = SRGB },
    TIFF16 = { format = octane.imageSaveFormat.TIFF_16, extension = "tif",
               colorSpace = SRGB },
    JPEG   = { format = octane.imageSaveFormat.JPEG,    extension = "jpg",
               colorSpace = SRGB },
    EXR16  = { format = octane.imageSaveFormat.EXR_16,  extension = "exr",
               colorSpace = LINEAR_SRGB },
    EXR32  = { format = octane.imageSaveFormat.EXR_32,  extension = "exr",
               colorSpace = LINEAR_SRGB },
}

local DISCRETE_FORMAT_PREFIX = "Discrete "
local DISCRETE_FORMAT_SUFFIX = "(s) (multipass)"
local LAYERED_FORMAT_PREFIX = "Layered "
local LAYERED_FORMAT_SUFFIX = " (multipass)"

io.stdout:setvbuf("no")
io.stderr:setvbuf("no")

local function sendToDaemon(payload)
    print(octane.json.encode(payload))
end

local function onError(text)
    print("openjd_fail: " .. text)
    error(text, 0)
end

local function startsWith(text, prefix)
    return string.sub(text, 1, #prefix) == prefix
end

local function endsWith(text, suffix)
    return string.sub(text, -#suffix) == suffix
end

-- Splits the OutputFormat job parameter into an image format and a pass mode:
--   "PNG8"                          -> PNG8,  single
--   "Discrete PNG8(s) (multipass)"  -> PNG8,  discrete
--   "Layered EXR16 (multipass)"     -> EXR16, layered
local function parseOutputFormat(label)
    label = string.match(label, "^%s*(.-)%s*$")
    if startsWith(label, DISCRETE_FORMAT_PREFIX)
            and endsWith(label, DISCRETE_FORMAT_SUFFIX) then
        return string.sub(label, #DISCRETE_FORMAT_PREFIX + 1,
            -#DISCRETE_FORMAT_SUFFIX - 1), "discrete"
    end
    if startsWith(label, LAYERED_FORMAT_PREFIX)
            and endsWith(label, LAYERED_FORMAT_SUFFIX) then
        return string.sub(label, #LAYERED_FORMAT_PREFIX + 1,
            -#LAYERED_FORMAT_SUFFIX - 1), "layered"
    end
    return label, "single"
end

local function knownFormatNames()
    local names = {}
    for name in pairs(IMAGE_FORMATS) do
        names[#names + 1] = name
    end
    table.sort(names)
    return table.concat(names, ", ")
end

local function parseStartupArguments(argv)
    local options = {}
    for _, entry in ipairs(argv or {}) do
        local key, value = string.match(entry, "^([%w%-]+)=(.*)$")
        if not key then
            onError("argument is not key=value: " .. tostring(entry))
        end
        options[key] = value
    end
    return options
end

local function optionalNumber(options, key)
    local raw = options[key]
    if raw == nil or raw == "" then
        return nil
    end
    local value = tonumber(raw)
    if not value then
        onError(key .. " must be a number, got '" .. raw .. "'")
    end
    return value
end

local function pinValue(node, pinName)
    if not node then
        return nil
    end
    local ok, value = pcall(octane.node.getPinValue, node, pinName)
    if not ok then
        return nil
    end
    return value
end

local function prepareSession(options)
    for _, required in ipairs({ "requests", "output-dir", "format", "template" }) do
        if not options[required] or options[required] == "" then
            onError("missing required argument " .. required .. "=")
        end
    end

    local formatName, passMode = parseOutputFormat(options["format"])
    local imageFormat = IMAGE_FORMATS[formatName]
    if not imageFormat then
        onError("could not read a known image format out of '"
            .. options["format"] .. "'. Expected one of " .. knownFormatNames()
            .. ", optionally as 'Discrete <format>(s) (multipass)' or 'Layered <format> "
            .. "(multipass)'")
    end
    if passMode == "layered" and not startsWith(formatName, "EXR") then
        onError("only EXR can hold layers, so '" .. formatName
            .. "' is not a valid layered format")
    end

    local sceneGraph = octane.project.getSceneGraph()
    if not sceneGraph then
        onError(
            "no scene is loaded. Pass the scene file to octane as its positional argument.")
    end

    local renderTargets = sceneGraph:findNodes(octane.NT_RENDERTARGET, true)
    local renderTarget, renderTargetIndex
    if options["target"] and options["target"] ~= "" then
        for index, item in ipairs(renderTargets) do
            if item.name == options["target"] then
                renderTarget, renderTargetIndex = item, index
                break
            end
        end
        if not renderTarget then
            local names = {}
            for _, item in ipairs(renderTargets) do
                names[#names + 1] = item.name
            end
            onError(string.format(
                "no render target named '%s' in the scene. Render targets present: %s",
                options["target"],
                #names > 0 and ("'" .. table.concat(names, "', '") .. "'") or "(none)"))
        end
        print("Render target from the job parameter: '" .. renderTarget.name .. "'")
    else
        renderTarget = octane.project.getPreviewRenderTarget()
        if not renderTarget then
            onError(
                "no render target was given and the scene carries no preview render target, "
                .. "so there is nothing to render. Set the Render Target Node parameter.")
        end
        renderTargetIndex = 0
        for index, item in ipairs(renderTargets) do
            if item.name == renderTarget.name then
                renderTargetIndex = index
                break
            end
        end
        print("No render target given, using the scene's preview render target: '"
            .. tostring(renderTarget.name) .. "'")
    end

    local framesPerSecond
    local requestedFramesPerSecond = optionalNumber(options, "fps")
    if requestedFramesPerSecond and requestedFramesPerSecond > 0 then
        framesPerSecond = requestedFramesPerSecond
        print(string.format("Frame rate from the job parameter: %g", framesPerSecond))
    else
        -- The project settings node holds its values as attributes rather than pins.
        local settings = octane.project.getProjectSettings()
        local ok, value = pcall(octane.node.getAttribute, settings,
            octane.A_FRAMES_PER_SECOND)
        if ok then
            framesPerSecond = tonumber(value)
        end
        if not framesPerSecond or framesPerSecond <= 0 then
            onError("could not read a frame rate from the scene, so set the Frame Rate "
                .. "parameter. Read back: " .. tostring(value))
        end
        print(string.format("Frame rate from the scene: %g", framesPerSecond))
    end

    local okAnimation, animationSettings = pcall(octane.node.getConnectedNode,
        renderTarget, "animation", true)
    if not okAnimation then
        animationSettings = nil
    end
    local requestedShutterTime = optionalNumber(options, "shutter-time")
    local shutterTimeFromJob = requestedShutterTime ~= nil and requestedShutterTime >= 0
    if shutterTimeFromJob then
        if not animationSettings then
            onError("render target '" .. tostring(renderTarget.name) .. "' has no "
                .. "animation settings node, so shutter time cannot be applied")
        end
        octane.node.setPinValue(animationSettings, "shutterTime", requestedShutterTime, true)
    end
    local shutterTime = pinValue(animationSettings, "shutterTime")
    print(string.format("Shutter time from the %s: %s",
        shutterTimeFromJob and "job parameter" or "scene", tostring(shutterTime)))

    -- Script-driven renders ignore --samples, so update the kernel node directly.
    local okKernel, kernelNode = pcall(octane.node.getConnectedNode, renderTarget,
        "kernel", true)
    if not okKernel then
        kernelNode = nil
    end
    local requestedMaxSamples = optionalNumber(options, "max-samples")
    local maxSamplesFromJob = requestedMaxSamples ~= nil and requestedMaxSamples >= 1
    if maxSamplesFromJob then
        if not kernelNode then
            onError("render target '" .. tostring(renderTarget.name) .. "' has no kernel "
                .. "node connected, so max-samples cannot be applied")
        end
        octane.node.setPinValue(kernelNode, "maxsamples", requestedMaxSamples, true)
    end
    local maxSamples = pinValue(kernelNode, "maxsamples")
    print(string.format("Max samples from the %s: %s (kernel '%s')",
        maxSamplesFromJob and "job parameter" or "scene", tostring(maxSamples),
        tostring(kernelNode and kernelNode.name)))

    -- Octane reports animation bounds in seconds; a static scene reports 0..0.
    local animationSpan = octane.nodegraph.getAnimationTimeSpan(sceneGraph)
    local animationStart, animationEnd = animationSpan[1], animationSpan[2]
    local isAnimated = animationEnd > animationStart
    -- Allow half a frame for floating-point rounding at the animation bounds.
    local animationSpanTolerance = 0.5 / framesPerSecond
    print(string.format(
        "Animation time span: %.4f to %.4f seconds, frames %g to %g at %g fps",
        animationStart, animationEnd,
        animationStart * framesPerSecond, animationEnd * framesPerSecond, framesPerSecond))
    if not isAnimated then
        print("WARNING: the scene reports no animation, so every frame renders identically.")
    end

    local enabledPasses = {}
    if passMode == "discrete" then
        local enabledPassIds = octane.render.getEnabledAovs(renderTarget)
        for _, passId in ipairs(enabledPassIds or {}) do
            local okInfo, info = pcall(octane.render.getRenderPassInfo, passId)
            enabledPasses[#enabledPasses + 1] = {
                id = passId,
                name = okInfo and info and info.name or tostring(passId),
            }
        end
        if #enabledPasses == 0 then
            onError("the format asks for one file per render pass, but the render target "
                .. "has no enabled render passes")
        end
        local names = {}
        for _, pass in ipairs(enabledPasses) do
            names[#names + 1] = pass.name
        end
        print(string.format("Enabled passes (%d): %s",
            #enabledPasses, table.concat(names, ", ")))
    end

    return {
        options = options,
        formatName = formatName,
        passMode = passMode,
        imageFormat = imageFormat,
        sceneGraph = sceneGraph,
        renderTarget = renderTarget,
        renderTargetIndex = renderTargetIndex,
        framesPerSecond = framesPerSecond,
        shutterTime = shutterTime,
        maxSamples = maxSamples,
        animationStart = animationStart,
        animationEnd = animationEnd,
        isAnimated = isAnimated,
        animationSpanTolerance = animationSpanTolerance,
        enabledPasses = enabledPasses,
        startupTimestamp = os.date("%H_%M_%S"),
    }
end

-- Expand once so percent signs in token values are not expanded again.
local function outputPath(session, frame, passName)
    local tokens = {
        f = string.format("%0" .. tostring(FRAME_NUMBER_PADDING) .. "d", frame),
        n = tostring(session.renderTarget.name),
        p = passName or "",
        e = session.imageFormat.extension,
        i = tostring(session.renderTargetIndex),
        t = session.startupTimestamp,
        ["%"] = "%",
    }
    local expandedName = string.gsub(session.options["template"], "%%(.)", function(key)
        local value = tokens[key]
        if value == nil then
            print("WARNING: unknown token '%" .. key .. "' in the filename template '"
                .. session.options["template"] .. "'")
        end
        return value
    end)
    return session.options["output-dir"] .. "/" .. expandedName
end

local function createParentDirectory(path)
    local parent = string.match(path, "^(.*)/[^/]*$")
    if not parent then
        return
    end
    -- createDirectory returns false when the directory already exists.
    if not octane.file.createDirectory(parent) and not octane.file.isDirectory(parent) then
        error("could not create the output directory '" .. parent .. "'", 0)
    end
end

local function warnBeforeOverwrite(path)
    if octane.file.exists(path) then
        print("WARNING: output file already exists and will be overwritten: '" .. path .. "'")
    end
end

-- Octane returns false instead of raising when a save fails.
local function saveRenderedFrame(session, frame)
    local writtenPaths = {}

    if session.passMode == "single" then
        local path = outputPath(session, frame, "Beauty")
        createParentDirectory(path)
        warnBeforeOverwrite(path)
        if not octane.render.saveImage3(path, session.imageFormat.format,
                session.imageFormat.colorSpace, octane.premultipliedAlphaType.NONE,
                nil, false) then
            error("no image was written for frame " .. tostring(frame), 0)
        end
        writtenPaths[#writtenPaths + 1] = path

    elseif session.passMode == "layered" then
        -- A layered EXR has no separate pass name for %p.
        local path = outputPath(session, frame, "")
        createParentDirectory(path)
        warnBeforeOverwrite(path)
        if not octane.render.saveRenderPassesMultiExr3(path, nil,
                session.formatName == "EXR16", session.imageFormat.colorSpace,
                octane.premultipliedAlphaType.NONE, nil, nil, false) then
            error("no layered EXR was written for frame " .. tostring(frame), 0)
        end
        writtenPaths[#writtenPaths + 1] = path

    else
        local hasPassToken = false
        for token in string.gmatch(session.options["template"], "%%(.)") do
            if token == "p" then
                hasPassToken = true
                break
            end
        end
        if not hasPassToken then
            print("WARNING: Discrete multipass output is selected, but the filename "
                .. "template has no %p token. Render passes may overwrite each other.")
        end

        -- saveRenderPass3 accepts a full path, avoiding collisions between frames.
        for index, pass in ipairs(session.enabledPasses) do
            print(string.format("openjd_status: frame %d, writing pass %d of %d: %s",
                frame, index, #session.enabledPasses, pass.name))
            local path = outputPath(session, frame, pass.name)
            createParentDirectory(path)
            warnBeforeOverwrite(path)
            if not octane.render.saveRenderPass3(pass.id, path,
                    session.imageFormat.format, session.imageFormat.colorSpace,
                    octane.premultipliedAlphaType.NONE, nil, false) then
                error(string.format("pass '%s' wrote no image for frame %d",
                    pass.name, frame), 0)
            end
            print(string.format("Wrote pass '%s' to %s", pass.name, path))
            -- render.start blocks, so progress covers only pass saves.
            print(string.format(
                "openjd_progress: %g", index / #session.enabledPasses * 100))
            writtenPaths[#writtenPaths + 1] = path
        end
    end

    return writtenPaths
end

local function renderFrame(session, frame)
    local timeInSeconds = frame / session.framesPerSecond
    print(string.format("Rendering frame %d at t=%.4fs", frame, timeInSeconds))

    if session.isAnimated
            and (timeInSeconds < session.animationStart - session.animationSpanTolerance
                or timeInSeconds > session.animationEnd + session.animationSpanTolerance) then
        print(string.format(
            "note: t=%.4fs is outside the scene's animation span of %.4f to %.4f, so "
            .. "Octane renders the nearest animated state and this frame will duplicate "
            .. "a neighbour.", timeInSeconds, session.animationStart, session.animationEnd))
    end

    -- Use wall-clock time because GPU work is not reflected in CPU time.
    local startedAt = os.time()
    octane.nodegraph.updateTime(session.sceneGraph, timeInSeconds, true)
    octane.render.start({
        renderTargetNode = session.renderTarget,
        doUpdate = true,
        -- Start each frame with an empty film buffer.
        restart = true,
    })
    local writtenPaths = saveRenderedFrame(session, frame)
    local elapsedSeconds = os.difftime(os.time(), startedAt)

    -- The reply closes the frame's output bracket.
    sendToDaemon({
        type = "reply",
        frame = frame,
        files = writtenPaths,
        message = string.format("frame %d wrote %d file(s) in %ds",
            frame, #writtenPaths, elapsedSeconds),
    })
end

local function frameFromRequest(requestLine)
    local ok, request = pcall(octane.json.decode, requestLine)
    if ok and type(request) == "table" then
        return tonumber(request.frame)
    end
    return nil
end

local function handleRequest(session, requestLine)
    local request = octane.json.decode(requestLine)
    if request.action ~= "render" then
        error("this server only understands the render action, got '"
            .. tostring(request.action) .. "'", 0)
    end
    local frame = tonumber(request.frame)
    if not frame then
        error("a render request needs a frame number, got: " .. requestLine, 0)
    end
    renderFrame(session, frame)
end

local function serveRequests(session)
    -- Keep one reader open so daemon writes cannot land between readers.
    local requestChannel = io.open(session.options["requests"], "r")
    if not requestChannel then
        onError("could not open the request channel at "
            .. tostring(session.options["requests"]))
    end

    while true do
        local requestLine = requestChannel:read("*l")
        if not requestLine then
            -- The daemon owns the writer, so EOF means it is gone.
            print("The request channel closed, shutting down")
            break
        end

        if requestLine ~= "" then
            -- Acknowledge first so all output, including failures, reaches this task.
            local frame = frameFromRequest(requestLine)
            sendToDaemon({ type = "ack", frame = frame })
            -- Octane omits Lua tracebacks, so capture one before stopping the server.
            local ok, problem = xpcall(
                handleRequest, debug.traceback, session, requestLine)
            if not ok then
                sendToDaemon({
                    type = "error",
                    frame = frame,
                    message = tostring(problem),
                })
                error(problem, 0)
            end
        end
    end

    requestChannel:close()
end

local function main()
    local options = parseStartupArguments(arg)
    local session = prepareSession(options)

    print("Scene loaded. Ready for render.")
    sendToDaemon({
        type = "ready",
        target = tostring(session.renderTarget.name),
        fps = session.framesPerSecond,
        shutterTime = session.shutterTime,
        maxSamples = session.maxSamples,
    })

    serveRequests(session)
end

main()
