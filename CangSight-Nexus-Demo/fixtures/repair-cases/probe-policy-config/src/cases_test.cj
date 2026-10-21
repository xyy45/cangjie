package probepolicyconfig

import std.unittest.*
import std.unittest.testmacro.*

@Test
class ProbeTests {
    @TestCase
    func target() {
        @Expect(requestedPath().isEmpty(), false)
    }

}
