import { createHmac } from "node:crypto";
import { execFileSync } from "node:child_process";

/** An invitation for a new user, made the way the operator makes one (`accounts_invite`, run in
 * the app container of the compose stack `make e2e` starts). Returns the token from the link. */
export function invite(email: string, name: string): string {
  const out = execFileSync(
    "docker",
    ["compose", "exec", "-T", "app", "python", "app/manage.py", "accounts_invite", email, "--name", name],
    { cwd: "..", encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] },
  );
  const token = /#(\S+)\s*$/.exec(out)?.[1];
  if (token === undefined) throw new Error("accounts_invite printed no link");
  return token;
}

const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

function base32(text: string): Buffer {
  let bits = "";
  for (const char of text.replace(/[\s=]/g, "").toUpperCase()) {
    bits += ALPHABET.indexOf(char).toString(2).padStart(5, "0");
  }
  const bytes: number[] = [];
  for (let at = 0; at + 8 <= bits.length; at += 8) bytes.push(parseInt(bits.slice(at, at + 8), 2));
  return Buffer.from(bytes);
}

/** RFC 6238 (SHA-1, 30 s, six digits). `steps` moves to a later or earlier 30-second step: the
 * server never takes one code twice, and accepts one step either side of its own clock. */
export function totp(secret: string, steps = 0, now = Date.now()): string {
  const counter = Math.floor(now / 30000) + steps;
  const message = Buffer.alloc(8);
  message.writeBigUInt64BE(BigInt(counter));
  const digest = createHmac("sha1", base32(secret)).update(message).digest();
  const offset = (digest[digest.length - 1] ?? 0) & 0x0f;
  const value = digest.readUInt32BE(offset) & 0x7fffffff;
  return String(value % 1_000_000).padStart(6, "0");
}
