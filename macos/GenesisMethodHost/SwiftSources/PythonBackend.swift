import Combine
import Foundation

/// Starts `genesis_app_launcher.py` (memory gate + WebUI). WKWebView loads localhost — no extra browser tab.
final class PythonBackend: ObservableObject {
    @Published private(set) var status: String = "Idle"
    @Published private(set) var serverReady: Bool = false

    private var process: Process?
    private var pollTimer: Timer?

    /// Base URL for WKWebView
    let dashboardURL = URL(string: "http://127.0.0.1:8123/")!

    /// Override if you use pyenv/homebrew python
    var pythonExecutable = "/usr/bin/python3"

    func start() {
        guard process == nil else { return }

        let root = GenesisPaths.resolvedGenesisRoot()
        guard FileManager.default.fileExists(atPath: root) else {
            status = "Genesis repo not found: \(root)"
            return
        }

        let launcher = (root as NSString).appendingPathComponent("genesis_app_launcher.py")
        guard FileManager.default.fileExists(atPath: launcher) else {
            status = "Missing genesis_app_launcher.py under \(root)"
            return
        }

        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: pythonExecutable)
        proc.arguments = [launcher]
        proc.currentDirectoryURL = URL(fileURLWithPath: root, isDirectory: true)

        var env = ProcessInfo.processInfo.environment
        env["GENESIS_ROOT"] = root
        env["GENESIS_WEBUI_OPEN_BROWSER"] = "0"
        proc.environment = env

        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = pipe

        do {
            try proc.run()
            process = proc
            status = "Python starting… (\(root))"
        } catch {
            status = "Failed to start Python: \(error.localizedDescription)"
            return
        }

        pollTimer?.invalidate()
        pollTimer = Timer.scheduledTimer(withTimeInterval: 0.35, repeats: true) { [weak self] timer in
            self?.checkPort(timer: timer)
        }
    }

    func stop() {
        pollTimer?.invalidate()
        pollTimer = nil
        process?.terminate()
        process = nil
        serverReady = false
        status = "Stopped"
    }

    deinit { stop() }

    private func checkPort(timer: Timer) {
        guard let proc = process, proc.isRunning else {
            timer.invalidate()
            status = "Python process exited"
            serverReady = false
            return
        }

        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/sbin/lsof")
        task.arguments = ["-nP", "-iTCP:8123", "-sTCP:LISTEN"]

        let pipe = Pipe()
        task.standardOutput = pipe
        task.standardError = FileHandle.nullDevice

        do {
            try task.run()
            task.waitUntilExit()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            let text = String(data: data, encoding: .utf8) ?? ""
            if text.contains(":8123") {
                timer.invalidate()
                serverReady = true
                status = "Dashboard ready"
            }
        } catch {
            // ignore transient errors
        }
    }
}
