func sum3(a: Int64, b: Int64, c: Int64): Int64 {
    let first = a + b
    let total = first + c
    return total
}
main(): Int64 {
    println(sum3(2, 3, 4))
    return 0
}
