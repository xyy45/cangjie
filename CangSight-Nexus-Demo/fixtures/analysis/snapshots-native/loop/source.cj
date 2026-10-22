func sumPositive(values: Array<Int64>): Int64 {
    var index: Int64 = 0
    var total: Int64 = 0
    while (index < values.size) {
        let value = values[index]
        if (value > 0) {
            total = total + value
        }
        index = index + 1
    }
    return total
}
main(): Int64 {
    println(sumPositive([2, -3, 4, 5]))
    println(sumPositive([7]))
    println(sumPositive([-2, -1]))
    return 0
}
