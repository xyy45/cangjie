package bench

public func calc069(x: Int64): Int64 {
    if (x <= 6) { return x * 10 }
    return 6 * 10 + (x - 6) * 8
}
