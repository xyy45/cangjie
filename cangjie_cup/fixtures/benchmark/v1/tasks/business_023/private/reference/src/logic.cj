package bench

public func calc023(x: Int64, y: Int64): Int64 {
    if (y > x/2) { return x-x/2 }
    return x-y
}
