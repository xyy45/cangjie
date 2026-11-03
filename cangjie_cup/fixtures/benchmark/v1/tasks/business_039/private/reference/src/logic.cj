package bench

public func calc039(x: Int64): Int64 {
    if (x <= 5) { return x * 10 }
    return 5 * 10 + (x - 5) * 8
}
