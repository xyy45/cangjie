package crossdiscount

import std.unittest.*
import std.unittest.testmacro.*

@Test
class CheckoutTests {
    @TestCase
    func threshold() {
        @Expect(discountFor(100), 10)
    }

    @TestCase
    func checkout() {
        @Expect(checkoutTotal(101), 91)
    }

    @TestCase
    func exact() {
        @Expect(checkoutTotal(100), 90)
    }

    @TestCase
    func below() {
        @Expect(checkoutTotal(99), 99)
    }

    @TestCase
    func zero() {
        @Expect(checkoutTotal(0), 0)
    }

    @TestCase
    func negative() {
        @Expect(checkoutTotal(-1), -1)
    }

    @TestCase
    func large() {
        @Expect(checkoutTotal(1000), 990)
    }

}
