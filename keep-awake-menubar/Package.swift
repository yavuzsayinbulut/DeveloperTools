// swift-tools-version: 6.1
import PackageDescription

let package = Package(
    name: "KeepAwake",
    platforms: [
        .macOS(.v13),
    ],
    products: [
        .executable(name: "KeepAwake", targets: ["KeepAwake"]),
    ],
    targets: [
        .executableTarget(
            name: "KeepAwake",
            path: "Sources/KeepAwake"
        ),
    ]
)
