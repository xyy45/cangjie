func clamp(value: Int64, lower: Int64, upper: Int64): Int64 {
    if (value < lower) {
        return lower
    }
    if (value > upper) {
        return upper
    }
    return value
}
func transform(value: Int64): Int64 {
    let bounded = clamp(value, -10, 10)
    return bounded * bounded
}
func aggregate(values: Array<Int64>): Int64 {
    var index: Int64 = 0
    var total: Int64 = 0
    while (index < values.size) {
        let value = values[index]
        let transformed = transform(value)
        total = total + transformed
        index = index + 1
    }
    return total
}
main(): Int64 {
    println(aggregate([2, -3, 20]))
    println(aggregate([0]))
    return 0
}
