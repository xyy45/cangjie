package bench

public func calc095(x: Int64, y: Int64): Int64 {
    if (y <= 0 || y > x) { return -1 }
    return x - y
}
