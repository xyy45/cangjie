package bench

public func calc099(x: Int64): Int64 {
    if (x <= 7) { return x * 10 }
    return 7 * 10 + (x - 7) * 8
}
