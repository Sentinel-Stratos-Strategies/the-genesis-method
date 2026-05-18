import SwiftUI

@main
struct GenesisMethodHostApp: App {
    @StateObject private var backend = PythonBackend()
    @StateObject private var pluginRegistry = GenesisPluginRegistry()

    var body: some Scene {
        WindowGroup {
            WebDashboardView(backend: backend, pluginRegistry: pluginRegistry)
                .frame(minWidth: 1100, minHeight: 820)
        }
        .commands {
            CommandGroup(replacing: .newItem) {}
        }
    }
}
