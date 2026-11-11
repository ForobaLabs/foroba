import { describe, expect, it } from "vitest";
import { friendlyRegisterError } from "./api";

describe("friendlyRegisterError", () => {
  it("hides the pydantic wording for reserved email domains", () => {
    const msg = friendlyRegisterError(
      "value is not a valid email address: The part after the @-sign is a special-use or reserved name",
    );
    expect(msg).not.toMatch(/pydantic|value is not|special-use/i);
    expect(msg).toMatch(/email address/i);
  });
  it("explains a duplicate account with a next step", () => {
    expect(friendlyRegisterError("Email already registered")).toMatch(/signing in/i);
  });
  it("states the 12-character password minimum", () => {
    expect(friendlyRegisterError("password too short")).toMatch(/12 characters/);
  });
  it("falls back to a generic, actionable message", () => {
    expect(friendlyRegisterError(undefined)).toMatch(/try again/i);
  });
});
