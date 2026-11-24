// Máscara del sujeto en primer plano con Vision (macOS 14+), para el efecto 3D de animar.py.
// Uso: swift mascara.swift <imagen> <mascara.png>   → PNG en escala de grises (blanco = primer plano).
// Sale con código 2 si Vision no encuentra un sujeto.
import Foundation
import Vision
import CoreImage

let args = CommandLine.arguments
guard args.count == 3 else { print("uso: mascara.swift <imagen> <salida.png>"); exit(1) }
let url = URL(fileURLWithPath: args[1])
let req = VNGenerateForegroundInstanceMaskRequest()
let handler = VNImageRequestHandler(url: url)
do { try handler.perform([req]) } catch { print("Vision: \(error)"); exit(1) }
guard let obs = req.results?.first, !obs.allInstances.isEmpty else { print("sin sujeto"); exit(2) }
let buf = try obs.generateScaledMaskForImage(forInstances: obs.allInstances, from: handler)
let ci = CIImage(cvPixelBuffer: buf)
let ctx = CIContext()
try ctx.writePNGRepresentation(of: ci, to: URL(fileURLWithPath: args[2]), format: .L8,
                               colorSpace: CGColorSpace(name: CGColorSpace.linearGray)!)
print("\(obs.allInstances.count) sujetos")
