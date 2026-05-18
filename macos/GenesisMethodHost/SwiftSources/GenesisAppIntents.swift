import AppIntents
import Foundation

struct OpenGenesisDashboardIntent: AppIntent {
    static var title: LocalizedStringResource = "Open Genesis Dashboard"
    static var description = IntentDescription("Open the native Genesis Method host and forensic dashboard.")
    static var openAppWhenRun = true

    func perform() async throws -> some IntentResult & ProvidesDialog {
        .result(dialog: "Opening Genesis Method.")
    }
}

struct ValidateGenesisPluginCatalogIntent: AppIntent {
    static var title: LocalizedStringResource = "Validate Genesis Plugin Catalog"
    static var description = IntentDescription("Check the Genesis Method plugin registry and report module coverage.")
    static var openAppWhenRun = false

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let root = GenesisPaths.resolvedGenesisRoot()
        let plugins = try await GenesisPluginRegistry.loadPlugins(root: root)
        let manifestCount = plugins.filter { $0.source == "manifest" }.count
        let pythonCount = plugins.filter { $0.source == "python" }.count
        let enabledCount = plugins.filter(\.defaultEnabled).count

        return .result(
            dialog: "Genesis indexed \(plugins.count) plugins: \(manifestCount) manifest-backed, \(pythonCount) Python-backed, \(enabledCount) enabled by default."
        )
    }
}

struct GenesisShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: OpenGenesisDashboardIntent(),
            phrases: [
                "Open \(.applicationName)",
                "Start \(.applicationName) dashboard"
            ],
            shortTitle: "Open Genesis",
            systemImageName: "shield.lefthalf.filled"
        )

        AppShortcut(
            intent: ValidateGenesisPluginCatalogIntent(),
            phrases: [
                "Validate \(.applicationName) plugins",
                "Check \(.applicationName) plugin coverage"
            ],
            shortTitle: "Check Plugins",
            systemImageName: "checklist"
        )
    }
}
