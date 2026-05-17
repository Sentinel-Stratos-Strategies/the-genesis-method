import Foundation

enum GenesisPaths {
    /// Absolute path to **The_Genesis_Method** repo (code only — evidence stays on Stratos/SENTINEL volumes).
    /// Option A: hardcode for your machine.
    static let genesisRepoPathHardcoded = "/Volumes/Stratos_Tools/projects/The_Genesis_Method"

    /// Option B: first line of `GENESIS_ROOT.txt` in the app bundle Resources (add file in Xcode → Copy Bundle Resources).
    static func genesisRootFromBundle() -> String? {
        guard let url = Bundle.main.url(forResource: "GENESIS_ROOT", withExtension: "txt") else { return nil }
        let line = (try? String(contentsOf: url, encoding: .utf8))?
            .split(separator: "\n")
            .first?
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard let line, !line.isEmpty else { return nil }
        return String(line)
    }

    static func resolvedGenesisRoot() -> String {
        if let fromBundle = genesisRootFromBundle(), FileManager.default.fileExists(atPath: fromBundle) {
            return fromBundle
        }
        return genesisRepoPathHardcoded
    }
}
