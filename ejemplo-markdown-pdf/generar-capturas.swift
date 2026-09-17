// Run on macOS: swift ejemplo-markdown-pdf/generar-capturas.swift
// Render the actual sample PDFs; this does not modify the PDFs or Markdown.
import AppKit
import PDFKit

enum PreviewError: Error {
    case missingPage(String, Int)
    case encodingFailed(String)
}

let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
let output = root.appendingPathComponent("capturas")
try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
let previews: [(String, Int, String)] = [
    ("basico.pdf", 0, "basico.png"),
    ("documento.pdf", 0, "portada.png"),
    ("documento.pdf", 1, "indice.png"),
    ("documento.pdf", 5, "tablas-figuras.png"),
    ("documento.pdf", 11, "mermaid.png"),
    ("documento.pdf", 12, "formulas-notas.png"),
]

for (file, index, name) in previews {
    guard let document = PDFDocument(url: root.appendingPathComponent(file)),
          let page = document.page(at: index) else {
        throw PreviewError.missingPage(file, index + 1)
    }
    let preview = page.thumbnail(of: NSSize(width: 1100, height: 1600), for: .mediaBox)
    guard let tiff = preview.tiffRepresentation,
          let bitmap = NSBitmapImageRep(data: tiff),
          let png = bitmap.representation(using: .png, properties: [:]) else {
        throw PreviewError.encodingFailed(name)
    }
    try png.write(to: output.appendingPathComponent(name), options: .atomic)
    print("\(file), página \(index + 1) → capturas/\(name)")
}
