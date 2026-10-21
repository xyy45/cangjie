package orderprice

import std.unittest.*
import std.unittest.testmacro.*

@Test
class PriceTests {
    @TestCase
    func upper() {
        @Expect(validPrice(1000000), true)
    }

    @TestCase
    func zero() {
        @Expect(validPrice(0), true)
    }

    @TestCase
    func normal() {
        @Expect(validPrice(99), true)
    }

    @TestCase
    func negative() {
        @Expect(validPrice(-1), false)
    }

    @TestCase
    func excess() {
        @Expect(validPrice(1000001), false)
    }

}
