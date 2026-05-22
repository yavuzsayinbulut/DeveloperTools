// swift-tools-version: 6.1
import PackageDescription

let package = Package(
    name: "DisplayAgent",
    platforms: [
        .macOS(.v13),
    ],
    products: [
        .executable(name: "DisplayAgent", targets: ["DisplayAgent"]),
    ],
    targets: [
        .executableTarget(
            name: "DisplayAgent",
            path: "Sources/DisplayAgent"
        ),
    ]
)
