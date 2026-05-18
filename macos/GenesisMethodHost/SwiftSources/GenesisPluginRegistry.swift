import Foundation

struct GenesisPlugin: Decodable, Identifiable, Hashable {
    let id: String
    let filename: String
    let name: String
    let category: String
    let target: String
    let description: String
    let defaultEnabled: Bool
    let source: String

    enum CodingKeys: String, CodingKey {
        case id
        case filename
        case name
        case category
        case target
        case description
        case defaultEnabled = "default_enabled"
        case source
    }
}

struct GenesisPluginSnapshot {
    let plugins: [GenesisPlugin]
    let loadedAt: Date
    let root: String

    var totalCount: Int { plugins.count }
    var defaultEnabledCount: Int { plugins.filter(\.defaultEnabled).count }

    var manifestCount: Int {
        plugins.filter { $0.source == "manifest" }.count
    }

    var pythonCount: Int {
        plugins.filter { $0.source == "python" }.count
    }

    var categories: [(name: String, count: Int)] {
        groupedCount(\.category)
    }

    var targets: [(name: String, count: Int)] {
        groupedCount(\.target)
    }

    var sources: [(name: String, count: Int)] {
        groupedCount(\.source)
    }

    private func groupedCount(_ keyPath: KeyPath<GenesisPlugin, String>) -> [(name: String, count: Int)] {
        let grouped = Dictionary(grouping: plugins, by: { $0[keyPath: keyPath] })
        return grouped
            .map { (name: $0.key, count: $0.value.count) }
            .sorted {
                if $0.count == $1.count { return $0.name < $1.name }
                return $0.count > $1.count
            }
    }
}

enum GenesisPluginRegistryError: LocalizedError {
    case missingRunner(String)
    case runnerFailed(String)
    case invalidOutput

    var errorDescription: String? {
        switch self {
        case .missingRunner(let path):
            "Missing plugin runner at \(path)"
        case .runnerFailed(let message):
            "Plugin registry command failed: \(message)"
        case .invalidOutput:
            "Plugin registry returned unreadable JSON."
        }
    }
}

@MainActor
final class GenesisPluginRegistry: ObservableObject {
    @Published private(set) var plugins: [GenesisPlugin] = []
    @Published private(set) var status: String = "Plugin registry not loaded"
    @Published private(set) var isLoading = false
    @Published private(set) var loadedAt: Date?
    @Published private(set) var lastError: String?

    var snapshot: GenesisPluginSnapshot {
        GenesisPluginSnapshot(
            plugins: plugins,
            loadedAt: loadedAt ?? Date.distantPast,
            root: GenesisPaths.resolvedGenesisRoot()
        )
    }

    func reload() {
        guard !isLoading else { return }
        isLoading = true
        status = "Indexing Genesis plugins..."
        lastError = nil

        Task {
            do {
                let root = GenesisPaths.resolvedGenesisRoot()
                let loadedPlugins = try await Self.loadPlugins(root: root)
                plugins = loadedPlugins
                loadedAt = Date()
                status = "\(loadedPlugins.count) Genesis plugins indexed"
            } catch {
                lastError = error.localizedDescription
                status = "Plugin registry unavailable"
            }
            isLoading = false
        }
    }

    nonisolated static func loadPlugins(root: String) async throws -> [GenesisPlugin] {
        try await Task.detached(priority: .userInitiated) {
            try loadPluginsSync(root: root)
        }.value
    }

    nonisolated static func loadPluginsSync(root: String) throws -> [GenesisPlugin] {
        let runner = (root as NSString).appendingPathComponent("tools/plugin_runner.py")
        let pluginDir = (root as NSString).appendingPathComponent("plugins")
        guard FileManager.default.fileExists(atPath: runner) else {
            throw GenesisPluginRegistryError.missingRunner(runner)
        }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        process.arguments = [runner, "--plugin-dir", pluginDir, "--list"]
        process.currentDirectoryURL = URL(fileURLWithPath: root, isDirectory: true)

        var environment = ProcessInfo.processInfo.environment
        environment["GENESIS_ROOT"] = root
        process.environment = environment

        let output = Pipe()
        let errors = Pipe()
        process.standardOutput = output
        process.standardError = errors

        try process.run()
        process.waitUntilExit()

        let outputData = output.fileHandleForReading.readDataToEndOfFile()
        let errorData = errors.fileHandleForReading.readDataToEndOfFile()
        let errorText = String(data: errorData, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines)

        guard process.terminationStatus == 0 else {
            throw GenesisPluginRegistryError.runnerFailed(errorText ?? "exit \(process.terminationStatus)")
        }

        do {
            let decoder = JSONDecoder()
            return try decoder.decode([GenesisPlugin].self, from: outputData)
        } catch {
            throw GenesisPluginRegistryError.invalidOutput
        }
    }
}
