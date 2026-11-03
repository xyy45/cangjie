func staged(a: Int64, b: Int64): Int64 {
    var value = a + 1
    let first = value * 2
    value = b + 3
    let second = value * 4
    return first + second
}
main(): Int64 {
    println(staged(2, 8))
    return 0
}
