package bench
import std.core.println as __nexusPrint0123456789abcdef
import std.unittest.*
import std.unittest.testmacro.*
@Test
class NexusProperties0123456789abcdef {
@TestCase
func case0() {
let __nexusTarget0123456789abcdef: (Int64, Int64, Int64) -> Int64 = refundState
let __nexusObserved = __nexusTarget0123456789abcdef(1000, 900, 200)
__nexusPrint0123456789abcdef("NEXUS_PROPERTY_V1|0123456789abcdef|case0|Int64|${__nexusObserved}")
}
@TestCase
func case1() {
let __nexusTarget0123456789abcdef: (Int64, Int64, Int64) -> Int64 = refundState
let __nexusObserved = __nexusTarget0123456789abcdef(1000, 800, 100)
__nexusPrint0123456789abcdef("NEXUS_PROPERTY_V1|0123456789abcdef|case1|Int64|${__nexusObserved}")
}
}
