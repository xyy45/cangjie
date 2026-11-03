package cangsightpolicy

import std.console.*
import stdx.encoding.json.*

func text(object: JsonObject, key: String): String {
    (object[key] as JsonString).getOrThrow().getValue()
}

func validHash(value: String): Bool {
    if (value.size != 64) { return false }
    for (byte in value.toArray()) {
        if (!((byte >= 48 && byte <= 57) || (byte >= 97 && byte <= 102))) { return false }
    }
    true
}

func decide(request: JsonObject): (String, String) {
    if (request.size() != 12) { return ("Deny", "INVALID_FIELDS") }
    let schema = (request["schema_version"] as JsonInt).getOrThrow().getValue()
    if (schema != 1 || text(request, "policy_version") != "1.1") {
        return ("Deny", "UNSUPPORTED_VERSION")
    }
    let deadline = (request["deadline_at"] as JsonInt).getOrThrow().getValue()
    let budget = (request["remaining_budget"] as JsonInt).getOrThrow().getValue()
    let accepted = (request["accepted"] as JsonBool).getOrThrow().getValue()
    let approval = text(request, "approval_binding")
    let paths = (request["paths"] as JsonArray).getOrThrow()
    if (deadline <= 0 || text(request, "request_id").isEmpty()) { return ("Deny", "INVALID_CONTEXT") }
    for (item in paths.getItems()) { let _ = (item as JsonString).getOrThrow() }
    let action = text(request, "action")
    let task = text(request, "task_id")
    let identity = text(request, "input_tree_hash")
    let arguments = text(request, "arguments_hash")
    if (task.isEmpty() || !validHash(identity) || !validHash(arguments)) {
        return ("Deny", "INVALID_CONTEXT")
    }
    if (action != "candidate.apply" && action != "candidate.build" &&
        action != "candidate.test" && action != "candidate.export" && action != "project.diagnose") {
        return ("Deny", "UNKNOWN_ACTION")
    }
    if (action == "candidate.apply") {
        if (budget <= 0 || budget > 3) {
            return ("Deny", "BUDGET_EXHAUSTED")
        }
        if (paths.size() < 1 || paths.size() > 3) {
            return ("Deny", "EDIT_COUNT")
        }
        for (item in paths.getItems()) {
            let path = (item as JsonString).getOrThrow().getValue()
            if (!path.startsWith("src/") || !path.endsWith(".cj") || path.endsWith("_test.cj") ||
                path.contains("..") || path.contains("\\") || path.contains("//")) {
                return ("Deny", "PROTECTED_PATH")
            }
        }
    }
    if (action == "candidate.export" && (!accepted || !validHash(approval))) {
        return ("NeedApproval", "ACCEPTANCE_REQUIRED")
    }
    return ("Allow", "PERMITTED")
}

main() {
    while (true) {
        let line = Console.stdIn.readln()
        if (line.isNone()) { break }
        let response = JsonObject()
        response.put("schema_version", JsonInt(1))
        response.put("policy_version", JsonString("1.1"))
        try {
            let input = line.getOrThrow()
            if (input.size + 1 > 65536) { throw Exception("MESSAGE_LIMIT") }
            let request = (JsonValue.fromStr(input) as JsonObject).getOrThrow()
            response.put("request_id", JsonString(text(request, "request_id")))
            response.put("arguments_hash", JsonString(text(request, "arguments_hash")))
            response.put("input_tree_hash", JsonString(text(request, "input_tree_hash")))
            response.put("approval_binding", JsonString(text(request, "approval_binding")))
            let (decision, reason) = decide(request)
            response.put("decision", JsonString(decision))
            response.put("reason", JsonString(reason))
        } catch (_: Exception) {
            response.put("decision", JsonString("Deny"))
            response.put("reason", JsonString("INVALID_REQUEST"))
        }
        Console.stdOut.writeln(response.toString())
        Console.stdOut.flush()
    }
    0
}
