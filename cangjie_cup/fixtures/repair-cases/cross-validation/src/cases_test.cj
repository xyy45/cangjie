package crossvalidation

import std.unittest.*
import std.unittest.testmacro.*

@Test
class ValidationTests {
    @TestCase
    func zeroQuantity() {
        @Expect(validQuantity(0), false)
    }

    @TestCase
    func multiply() {
        @Expect(calculateFee(3, 100), 300)
    }

    @TestCase
    func minimum() {
        @Expect(validQuantity(1), true)
    }

    @TestCase
    func maximum() {
        @Expect(validQuantity(1000), true)
    }

    @TestCase
    func negative() {
        @Expect(validQuantity(-1), false)
    }

    @TestCase
    func tooMany() {
        @Expect(validQuantity(1001), false)
    }

    @TestCase
    func normal() {
        @Expect(processOrder(2, 100), 200)
    }

    @TestCase
    func zeroPrice() {
        @Expect(processOrder(1, 0), 0)
    }

    @TestCase
    func negativePrice() {
        @Expect(processOrder(1, -1), -1)
    }

}
