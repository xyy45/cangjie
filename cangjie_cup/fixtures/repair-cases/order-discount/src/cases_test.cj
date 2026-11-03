package orderdiscount

import std.unittest.*
import std.unittest.testmacro.*

@Test
class DiscountTests {
    @TestCase
    func threshold() {
        @Expect(discountFor(100), 10)
    }

    @TestCase
    func below() {
        @Expect(discountFor(99), 0)
    }

    @TestCase
    func above() {
        @Expect(discountFor(101), 10)
    }

    @TestCase
    func zero() {
        @Expect(discountFor(0), 0)
    }

    @TestCase
    func negative() {
        @Expect(discountFor(-1), -1)
    }

}
