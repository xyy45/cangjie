package orderdemo

import std.unittest.*
import std.unittest.testmacro.*

@Test
class OrderTests {
    @TestCase
    func three() {
        @Expect(processOrder(3, 100), 300)
    }

    @TestCase
    func two() {
        @Expect(processOrder(2, 100), 200)
    }

    @TestCase
    func zeroPrice() {
        @Expect(processOrder(1, 0), 0)
    }

    @TestCase
    func zeroQuantity() {
        @Expect(processOrder(0, 100), -1)
    }

    @TestCase
    func negativeQuantity() {
        @Expect(processOrder(-1, 100), -1)
    }

    @TestCase
    func upperQuantity() {
        @Expect(processOrder(1000, 100), 100000)
    }

    @TestCase
    func excessQuantity() {
        @Expect(processOrder(1001, 100), -1)
    }

    @TestCase
    func negativePrice() {
        @Expect(processOrder(1, -1), -1)
    }

    @TestCase
    func upperPrice() {
        @Expect(processOrder(1, 1000000), 1000000)
    }

    @TestCase
    func excessPrice() {
        @Expect(processOrder(1, 1000001), -1)
    }

    @TestCase
    func differentPrice() {
        @Expect(processOrder(7, 23), 161)
    }

}
