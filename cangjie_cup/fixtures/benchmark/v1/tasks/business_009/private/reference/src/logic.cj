package bench

public func calc009(x: Int64): Int64 {
    if (x <= 4) { return x * 10 }
    return 4 * 10 + (x - 4) * 8
}
