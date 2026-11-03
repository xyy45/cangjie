package bench

public func hard025(total: Int64, periods: Int64, index: Int64): Int64 {
    if (periods < 1 || index < 0 || index > periods) { return -1 }
    let base = total / periods
    if (index == periods) { return total - base * (periods - 1) }
    return base
}
