package cangsightcore

import std.console.*
import stdx.encoding.json.*

func text(object: JsonObject, key: String): String {
    (object[key] as JsonString).getOrThrow().getValue()
}

func number(object: JsonObject, key: String): Int64 {
    (object[key] as JsonInt).getOrThrow().getValue()
}

func validHash(value: String): Bool {
    if (value.size != 64) { return false }
    for (byte in value.toArray()) {
        if (!((byte >= 48 && byte <= 57) || (byte >= 97 && byte <= 102))) { return false }
    }
    true
}

func addUnique(values: JsonArray, value: Int64, lower: Int64, upper: Int64): Unit {
    if (value < lower || value > upper) { return }
    for (item in values.getItems()) {
        if ((item as JsonInt).getOrThrow().getValue() == value) { return }
    }
    values.add(JsonInt(value))
}

func addNeighbors(values: JsonArray, point: Int64, lower: Int64, upper: Int64): Unit {
    addUnique(values, point, lower, upper)
    // Check representability before arithmetic: Int64 extrema never wrap.
    if (point > -9223372036854775808) { addUnique(values, point - 1, lower, upper) }
    if (point < 9223372036854775807) { addUnique(values, point + 1, lower, upper) }
}

func validObjectName(value: String): Bool {
    if (value.isEmpty() || value.size > 64) { return false }
    let bytes = value.toArray()
    if (bytes[0] >= 48 && bytes[0] <= 57) { return false }
    for (byte in bytes) {
        if (!((byte >= 65 && byte <= 90) || (byte >= 97 && byte <= 122) ||
              (byte >= 48 && byte <= 57) || byte == 95)) { return false }
    }
    let reserved = ["Any", "Array", "Bool", "CString", "Float16", "Float32", "Float64", "Int16", "Int32", "Int64", "Int8", "IntNative", "Nothing", "Object", "Rune", "String", "UInt16", "UInt32", "UInt64", "UInt8", "UIntNative", "Unit", "break", "case", "catch", "class", "continue", "else", "enum", "eprint", "eprintln", "exit", "extend", "false", "finally", "for", "foreign", "func", "if", "import", "in", "init", "interface", "let", "main", "match", "mut", "open", "override", "package", "panic", "print", "println", "private", "prop", "protected", "public", "readln", "return", "sleep", "static", "struct", "this", "throw", "true", "try", "type", "unsafe", "var", "while"]
    for (word in reserved) { if (value == word) { return false } }
    true
}

func verificationPackageName(value: String): Bool {
    let prefix = "nexus_verify_".toArray()
    let bytes = value.toArray()
    if (bytes.size < prefix.size) { return false }
    var index: Int64 = 0
    while (index < prefix.size) {
        var byte = bytes[index]
        if (byte >= 65 && byte <= 90) { byte += 32 }
        if (byte != prefix[index]) { return false }
        index += 1
    }
    true
}

func validObjectTypeName(value: String): Bool {
    if (!value.contains(".")) { return validObjectName(value) }
    if (value.size > 256 || value.startsWith(".") || value.endsWith(".") || value.contains("..")) {
        return false
    }
    let parts = value.split(".")
    if (parts.size < 2 || parts.size > 9 || parts[0] == "std" || parts[0] == "cangjie") { return false }
    if (value.size - parts[parts.size - 1].size - 1 > 191) { return false }
    var index: Int64 = 0
    for (part in parts) {
        if (!validObjectName(part) || part == "as") { return false }
        if (index < parts.size - 1 && verificationPackageName(part)) { return false }
        index += 1
    }
    true
}

func objectLeaf(value: JsonValue, kind: String): JsonValue {
    if (kind == "Int64") { return JsonInt((value as JsonInt).getOrThrow().getValue()) }
    if (kind == "Bool") { return JsonBool((value as JsonBool).getOrThrow().getValue()) }
    if (kind == "String") {
        let item = (value as JsonString).getOrThrow().getValue()
        if (item.size > 256) { throw Exception("OBJECT_STRING_LIMIT") }
        return JsonString(item)
    }
    if (kind == "Array<Int64>") {
        let array = (value as JsonArray).getOrThrow()
        if (array.size() > 16) { throw Exception("OBJECT_ARRAY_LIMIT") }
        let result = JsonArray()
        for (item in array.getItems()) { result.add(JsonInt((item as JsonInt).getOrThrow().getValue())) }
        return result
    }
    throw Exception("OBJECT_FIELD_TYPE")
}

func objectRegistry(types: JsonObject): JsonObject {
    if (types.size() < 1 || types.size() > 4) { throw Exception("OBJECT_TYPE_COUNT") }
    for ((name, raw) in types.getFields()) {
        if (!validObjectTypeName(name)) { throw Exception("OBJECT_TYPE_NAME") }
        let item = (raw as JsonObject).getOrThrow()
        if (item.size() != 2) { throw Exception("OBJECT_TYPE_FIELDS") }
        let kind = text(item, "kind")
        if (kind != "struct" && kind != "class") { throw Exception("OBJECT_KIND") }
        let fields = (item["fields"] as JsonArray).getOrThrow()
        if (fields.size() < 1 || fields.size() > 4) { throw Exception("OBJECT_FIELD_COUNT") }
        let seen = JsonObject()
        for (entry in fields.getItems()) {
            let field = (entry as JsonObject).getOrThrow()
            if (field.size() != 2) { throw Exception("OBJECT_FIELD_KEYS") }
            let fieldName = text(field, "name")
            let fieldType = text(field, "type")
            if (!validObjectName(fieldName) || seen.containsKey(fieldName)) { throw Exception("OBJECT_FIELD_NAME") }
            if (fieldType != "Int64" && fieldType != "Bool" && fieldType != "String" && fieldType != "Array<Int64>") {
                throw Exception("OBJECT_FIELD_TYPE")
            }
            seen.put(fieldName, JsonBool(true))
        }
    }
    types
}

func objectValue(raw: JsonValue, name: String, types: JsonObject): JsonObject {
    let value = (raw as JsonObject).getOrThrow()
    if (value.size() != 2 || text(value, "$type") != name) { throw Exception("OBJECT_TAG") }
    let fields = (value["fields"] as JsonObject).getOrThrow()
    let declaration = (types[name] as JsonObject).getOrThrow()
    let declared = (declaration["fields"] as JsonArray).getOrThrow()
    if (fields.size() != declared.size()) { throw Exception("OBJECT_FIELDS") }
    let checked = JsonObject()
    for (rawField in declared.getItems()) {
        let field = (rawField as JsonObject).getOrThrow()
        let key = text(field, "name")
        checked.put(key, objectLeaf(fields[key], text(field, "type")))
    }
    let result = JsonObject()
    result.put("$type", JsonString(name))
    result.put("fields", checked)
    result
}

func objectKey(value: JsonObject, name: String, types: JsonObject): String {
    let fields = (value["fields"] as JsonObject).getOrThrow()
    let declared = ((types[name] as JsonObject).getOrThrow()["fields"] as JsonArray).getOrThrow()
    var key = name + ":"
    for (rawField in declared.getItems()) {
        let field = (rawField as JsonObject).getOrThrow()
        let encoded = fields[text(field, "name")].toString()
        key += encoded.size.toString() + ":" + encoded
    }
    key
}

func boundaryAxes(payload: JsonObject): JsonObject {
    var types = JsonObject()
    if (payload.containsKey("types")) {
        if (payload.size() != 2) { throw Exception("INVALID_FIELDS") }
        types = objectRegistry((payload["types"] as JsonObject).getOrThrow())
    } else if (payload.size() != 1) { throw Exception("INVALID_FIELDS") }
    let domains = (payload["domains"] as JsonArray).getOrThrow()
    if (domains.size() > 16) { throw Exception("DOMAIN_COUNT") }
    let names = JsonArray()
    let axes = JsonArray()
    for (item in domains.getItems()) {
        let parameter = (item as JsonObject).getOrThrow()
        if (parameter.size() != 3) { throw Exception("INVALID_PARAMETER") }
        let name = text(parameter, "name")
        if (name.isEmpty() || name.size > 128) { throw Exception("INVALID_NAME") }
        for (old in names.getItems()) {
            if ((old as JsonString).getOrThrow().getValue() == name) { throw Exception("DUPLICATE_NAME") }
        }
        names.add(JsonString(name))
        let kind = text(parameter, "type")
        let domain = (parameter["domain"] as JsonObject).getOrThrow()
        let values = JsonArray()
        if (types.containsKey(kind)) {
            if (domain.size() != 1) { throw Exception("INVALID_OBJECT_DOMAIN") }
            let objects = (domain["values"] as JsonArray).getOrThrow()
            if (objects.size() < 1 || objects.size() > 16) { throw Exception("OBJECT_DOMAIN_COUNT") }
            let seen = JsonObject()
            for (rawObject in objects.getItems()) {
                let value = objectValue(rawObject, kind, types)
                let key = objectKey(value, kind, types)
                if (seen.containsKey(key)) { throw Exception("DUPLICATE_OBJECT_VALUE") }
                seen.put(key, JsonBool(true))
                values.add(value)
            }
        } else if (kind == "Bool") {
            if (domain.size() != 0) { throw Exception("INVALID_BOOL_DOMAIN") }
            values.add(JsonBool(false))
            values.add(JsonBool(true))
        } else if (kind == "Int64") {
            if (domain.size() != 3) { throw Exception("INVALID_INTEGER_DOMAIN") }
            let lower = number(domain, "min")
            let upper = number(domain, "max")
            let points = (domain["points"] as JsonArray).getOrThrow()
            if (lower > upper || points.size() > 8) { throw Exception("INVALID_RANGE") }
            var base: Int64 = 0
            if (base < lower) { base = lower }
            if (base > upper) { base = upper }
            addUnique(values, base, lower, upper)
            addUnique(values, lower, lower, upper)
            addUnique(values, upper, lower, upper)
            for (rawPoint in points.getItems()) {
                let point = (rawPoint as JsonInt).getOrThrow().getValue()
                if (point < lower || point > upper) { throw Exception("INVALID_POINT") }
                addNeighbors(values, point, lower, upper)
            }
            addNeighbors(values, lower, lower, upper)
            addNeighbors(values, upper, lower, upper)
            addNeighbors(values, 0, lower, upper)
        } else if (kind == "Array<Int64>") {
            if (domain.size() != 1) { throw Exception("INVALID_ARRAY_DOMAIN") }
            let arrays = (domain["values"] as JsonArray).getOrThrow()
            if (arrays.size() < 1 || arrays.size() > 16) { throw Exception("ARRAY_DOMAIN_COUNT") }
            for (item in arrays.getItems()) {
                let value = (item as JsonArray).getOrThrow()
                if (value.size() > 16) { throw Exception("ARRAY_LENGTH_LIMIT") }
                for (element in value.getItems()) { let _ = (element as JsonInt).getOrThrow().getValue() }
                for (old in values.getItems()) {
                    if (old.toString() == value.toString()) { throw Exception("DUPLICATE_ARRAY_VALUE") }
                }
                values.add(value)
            }
        } else if (kind == "String") {
            if (domain.size() != 1) { throw Exception("INVALID_STRING_DOMAIN") }
            let strings = (domain["values"] as JsonArray).getOrThrow()
            if (strings.size() < 1 || strings.size() > 16) { throw Exception("STRING_DOMAIN_COUNT") }
            for (item in strings.getItems()) {
                let value = (item as JsonString).getOrThrow().getValue()
                if (value.size > 256) { throw Exception("STRING_BYTE_LIMIT") }
                for (old in values.getItems()) {
                    if ((old as JsonString).getOrThrow().getValue() == value) { throw Exception("DUPLICATE_STRING_VALUE") }
                }
                values.add(JsonString(value))
            }
        } else {
            throw Exception("UNSUPPORTED_TYPE")
        }
        axes.add(values)
    }
    let result = JsonObject()
    result.put("axes", axes)
    result
}

func decision(value: String, reason: String): JsonObject {
    let result = JsonObject()
    result.put("decision", JsonString(value))
    result.put("reason", JsonString(reason))
    result
}

func policyDecision(request: JsonObject): JsonObject {
    if (request.size() != 13 || number(request, "schema_version") != 1 ||
        text(request, "policy_version") != "2.0") { throw Exception("INVALID_POLICY") }
    let action = text(request, "action")
    let task = text(request, "task_id")
    let deadline = number(request, "deadline_at")
    let budget = number(request, "remaining_budget")
    let accepted = (request["accepted"] as JsonBool).getOrThrow().getValue()
    let approvalBinding = text(request, "approval_binding")
    let paths = (request["paths"] as JsonArray).getOrThrow()
    let facts = (request["facts"] as JsonObject).getOrThrow()
    if (facts.size() != 14 || task.isEmpty() || text(request, "request_id").isEmpty() ||
        !validHash(text(request, "input_tree_hash")) || !validHash(text(request, "arguments_hash")) ||
        task != text(facts, "task_id") || task != text(facts, "subject_task_id") ||
        text(facts, "subject_id").isEmpty() || !validHash(text(facts, "task_hash")) ||
        number(facts, "revision") < 0 || number(facts, "now_ms") <= 0 ||
        deadline <= number(facts, "now_ms") || budget < 0 || budget > 3 ||
        text(facts, "tree_hash") != text(request, "input_tree_hash")) {
        return decision("Deny", "INVALID_CONTEXT")
    }
    let spec = text(facts, "spec_hash")
    let plan = text(facts, "verification_plan_hash")
    if (!((spec.isEmpty() && plan.isEmpty()) || (validHash(spec) && validHash(plan)))) {
        return decision("Deny", "INVALID_VERSION_BINDING")
    }
    let state = text(facts, "status")
    let allowed = (facts["allowed_paths"] as JsonArray).getOrThrow()
    let approval = (facts["approval"] as JsonObject).getOrThrow()
    let exportVerified = (facts["export_verified"] as JsonBool).getOrThrow().getValue()
    let checkSet = text(facts, "check_set_hash")
    for (path in paths.getItems()) { let _ = (path as JsonString).getOrThrow() }
    for (path in allowed.getItems()) { let _ = (path as JsonString).getOrThrow() }
    if (action == "candidate.apply") {
        if (state != "READY" && state != "APPLYING") { return decision("Deny", "INVALID_TASK_STATE") }
        if (budget < 1) { return decision("Deny", "BUDGET_EXHAUSTED") }
        if (paths.size() < 1 || paths.size() > 3) { return decision("Deny", "EDIT_COUNT") }
        let seen = JsonArray()
        for (item in paths.getItems()) {
            let path = (item as JsonString).getOrThrow().getValue()
            if (!path.startsWith("src/") || !path.endsWith(".cj") || path.endsWith("_test.cj") ||
                path.contains("..") || path.contains("\\") || path.contains("//") || path.contains("/./")) {
                return decision("Deny", "PROTECTED_PATH")
            }
            for (previous in seen.getItems()) {
                if ((previous as JsonString).getOrThrow().getValue() == path) { return decision("Deny", "DUPLICATE_PATH") }
            }
            seen.add(JsonString(path))
            var permitted = false
            for (entry in allowed.getItems()) {
                if ((entry as JsonString).getOrThrow().getValue() == path) { permitted = true }
            }
            if (!permitted) { return decision("Deny", "OUTSIDE_SCOPE") }
        }
    } else if (action == "project.diagnose") {
        if (state != "READY" && state != "DIAGNOSING") { return decision("Deny", "INVALID_TASK_STATE") }
    } else if (action == "candidate.build") {
        if (state != "READY" && state != "BUILDING") { return decision("Deny", "INVALID_TASK_STATE") }
    } else if (action == "candidate.test") {
        if (state != "READY" && state != "TESTING") { return decision("Deny", "INVALID_TASK_STATE") }
    } else if (action == "candidate.export") {
        if (state != "REVIEW_PENDING" && state != "EXPORTING" && !(state == "DELIVERED" && exportVerified)) {
            return decision("Deny", "INVALID_TASK_STATE")
        }
        if (!accepted || !validHash(approvalBinding) || approval.size() != 7 || !validHash(checkSet)) {
            return decision("NeedApproval", "ACCEPTANCE_REQUIRED")
        }
        if (text(approval, "task_id") != task || text(approval, "candidate_id") != text(facts, "subject_id") ||
            text(approval, "tree_hash") != text(facts, "tree_hash") || text(approval, "spec_hash") != spec ||
            text(approval, "verification_plan_hash") != plan || text(approval, "check_set_hash") != checkSet ||
            number(approval, "expires_at_ms") <= number(facts, "now_ms")) {
            return decision("NeedApproval", "APPROVAL_VERSION_CHANGED")
        }
    } else {
        return decision("Deny", "UNKNOWN_ACTION")
    }
    if (action != "candidate.apply" && paths.size() != 0) { return decision("Deny", "UNEXPECTED_PATHS") }
    decision("Allow", "PERMITTED")
}

func knownState(state: String): Bool {
    state == "READY" || state == "DIAGNOSING" || state == "GENERATING" || state == "APPLYING" ||
    state == "BUILDING" || state == "TESTING" || state == "REVIEW_PENDING" || state == "EXPORTING" ||
    state == "DELIVERED" || state == "BLOCKED" || state == "IN_DOUBT" || state == "UNREPAIRED" ||
    state == "REJECTED" || state == "CANCELLED"
}

func transitionDecision(payload: JsonObject): JsonObject {
    if (payload.size() != 8 || text(payload, "task_id").isEmpty()) { throw Exception("INVALID_TRANSITION") }
    let before = text(payload, "from_status")
    let after = text(payload, "to_status")
    let revision = number(payload, "revision")
    let attempt = number(payload, "attempt_count")
    let nextAttempt = number(payload, "next_attempt_count")
    if (!knownState(before) || !knownState(after) || revision < 0 || revision == 9223372036854775807 ||
        number(payload, "expected_revision") != revision || number(payload, "new_revision") != revision + 1 ||
        attempt < 0 || attempt > 3 || nextAttempt < attempt || nextAttempt > 3) {
        return decision("Deny", "INVALID_TRANSITION_VERSION")
    }
    let terminal = before == "DELIVERED" || before == "CANCELLED" || before == "REJECTED" || before == "BLOCKED" ||
        before == "IN_DOUBT" || before == "UNREPAIRED"
    if (terminal && (before != after || nextAttempt != attempt)) { return decision("Deny", "TERMINAL_STATE") }
    if (before == after) { return decision("Allow", "PERMITTED") }
    if (after == "BLOCKED" || after == "IN_DOUBT" || after == "UNREPAIRED" || after == "CANCELLED" || after == "REJECTED") {
        return decision("Allow", "PERMITTED")
    }
    // READY also supports the existing explicit manual SDK verification flow.
    let permitted = (before == "READY" && (after == "DIAGNOSING" || after == "GENERATING" || after == "APPLYING" ||
            after == "BUILDING" || after == "TESTING" || after == "REVIEW_PENDING")) ||
        (before == "DIAGNOSING" && after == "GENERATING") ||
        (before == "GENERATING" && after == "APPLYING") ||
        (before == "APPLYING" && after == "BUILDING") ||
        (before == "BUILDING" && (after == "TESTING" || after == "GENERATING")) ||
        (before == "TESTING" && (after == "GENERATING" || after == "REVIEW_PENDING")) ||
        (before == "REVIEW_PENDING" && after == "EXPORTING") ||
        (before == "EXPORTING" && (after == "DELIVERED" || after == "REVIEW_PENDING"))
    if (!permitted) { return decision("Deny", "INVALID_STATE_TRANSITION") }
    decision("Allow", "PERMITTED")
}

main() {
    while (true) {
        let line = Console.stdIn.readln()
        if (line.isNone()) { break }
        let response = JsonObject()
        response.put("schema_version", JsonInt(1))
        response.put("core_version", JsonString("2.0"))
        response.put("status", JsonString("ERROR"))
        response.put("reason", JsonString("INVALID_REQUEST"))
        response.put("data", JsonObject())
        try {
            let input = line.getOrThrow()
            if (input.size + 1 > 65536) { throw Exception("MESSAGE_LIMIT") }
            let request = (JsonValue.fromStr(input) as JsonObject).getOrThrow()
            if (request.size() != 6 || number(request, "schema_version") != 1 ||
                text(request, "core_version") != "2.0") { throw Exception("INVALID_ENVELOPE") }
            let operation = text(request, "operation")
            let requestId = text(request, "request_id")
            let payloadHash = text(request, "payload_hash")
            if (requestId.isEmpty() || requestId.size > 128 || !validHash(payloadHash)) {
                throw Exception("INVALID_BINDING")
            }
            response.put("operation", JsonString(operation))
            response.put("request_id", JsonString(requestId))
            response.put("payload_hash", JsonString(payloadHash))
            let payload = (request["payload"] as JsonObject).getOrThrow()
            if (operation == "boundary.axes") {
                response.put("data", boundaryAxes(payload))
            } else if (operation == "policy.decide") {
                response.put("data", policyDecision(payload))
            } else if (operation == "task.transition") {
                response.put("data", transitionDecision(payload))
            } else {
                throw Exception("UNKNOWN_OPERATION")
            }
            response.put("status", JsonString("OK"))
            response.put("reason", JsonString("COMPLETED"))
        } catch (_: Exception) {
            // Invalid or unsupported input never produces a successful result.
        }
        Console.stdOut.writeln(response.toString())
        Console.stdOut.flush()
    }
    0
}
