// swift-tools-version: 6.1
import PackageDescription

let package = Package(
    name: "WindowPinner",
    platforms: [
        .macOS(.v13),
    ],
    products: [
        .executable(name: "WindowPinner", targets: ["WindowPinner"]),
    ],
    targets: [
        .executableTarget(
            name: "WindowPinner",
            path: "Sources/WindowPinner"
        ),
    ]
)
