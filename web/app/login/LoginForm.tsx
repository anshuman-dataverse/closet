"use client";

import { useSearchParams } from "next/navigation";
import { useActionState } from "react";
import { type LoginState, sendLink, verifyCode } from "./actions";

const ERRORS: Record<string, string> = {
  "not-allowed": "That email can’t use this closet. Sign in with the owner’s email.",
  link: "That sign-in link didn’t work or has expired. Ask for a new one.",
};

export function LoginForm() {
  const params = useSearchParams();
  const next = params.get("next") ?? "";
  const urlError = ERRORS[params.get("error") ?? ""];
  const [sent, send, sending] = useActionState<LoginState, FormData>(sendLink, { step: "email", email: "" });
  const [checked, check, checking] = useActionState<LoginState, FormData>(
    (prev, form) => verifyCode({ ...prev, email: sent.email }, form),
    { step: "code", email: "" },
  );

  if (sent.step === "code") {
    return (
      <form action={check}>
        <p className="lead">Check your email for a sign-in link and a 6-digit code.</p>
        <p className="muted small">
          On your iPhone’s Home Screen app, type the code here. The link opens in Safari instead.
        </p>
        <input type="hidden" name="next" value={next} />
        <label className="field">
          <span>6-digit code</span>
          <input
            type="text"
            name="code"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9 ]{6,7}"
            maxLength={7}
            required
            autoFocus
          />
        </label>
        <p className="err" role="alert">
          {checked.error ?? ""}
        </p>
        <div className="row">
          <button type="submit" className="btn primary" disabled={checking}>
            {checking ? "Signing in…" : "Sign in"}
          </button>
          <button type="button" className="btn ghost" onClick={() => window.location.reload()}>
            Use a different email
          </button>
        </div>
      </form>
    );
  }

  return (
    <form action={send}>
      <p className="lead">Sign in with your email. You’ll get a link and a code.</p>
      <input type="hidden" name="next" value={next} />
      <label className="field">
        <span>Email</span>
        <input type="email" name="email" autoComplete="email" required defaultValue={sent.email} />
      </label>
      <p className="err" role="alert">
        {sent.error ?? urlError ?? ""}
      </p>
      <div className="row">
        <button type="submit" className="btn primary" disabled={sending}>
          {sending ? "Sending…" : "Email me a sign-in link"}
        </button>
      </div>
    </form>
  );
}
