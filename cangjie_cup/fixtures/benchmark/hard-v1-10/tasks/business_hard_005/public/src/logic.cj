package bench

public func hard005(total: Int64, periods: Int64, index: Int64): Int64 {
    if (periods < 1 || index < 1 || index > periods) { return -1 }
    return total / periods
}
