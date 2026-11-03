package bench

public func calc014(x: Int64, y: Int64): Int64 {
    if (y <= 0 || y >= x) { return -1 }
    return x-y
}
