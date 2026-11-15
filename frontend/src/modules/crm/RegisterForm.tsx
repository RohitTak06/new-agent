import React, { useState } from "react";
import { ApiError, errorMessage } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { Button, ErrorBanner, Loading } from "../../lib/ui";
import { useApi } from "../../lib/useApi";
import type { RegisterOptions, Registration, User } from "../../lib/types";

type Field = "first_name" | "last_name" | "email" | "phone" | "state" | "city" | "course" | "password" | "confirm" | "consent";
type Errors = Partial<Record<Field, string>>;

const CONSENT_TEXT = "I agree to be contacted by the university about my application by email, SMS, WhatsApp and phone.";
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/** The same rules the server applies, so a student sees a problem before sending. The server checks them again. */
function validate(form: Registration, confirm: string, minPassword: number): Errors {
  const errors: Errors = {};
  if (!form.first_name.trim()) errors.first_name = "Enter your first name";
  if (!form.last_name.trim()) errors.last_name = "Enter your last name";
  if (!EMAIL.test(form.email.trim())) errors.email = "Enter a valid email address";
  if (!/^\d{10}$/.test(form.phone.replace(/[\s-]/g, ""))) errors.phone = "Enter a 10-digit mobile number";
  if (!form.state) errors.state = "Choose your state";
  if (!form.city.trim()) errors.city = "Enter your city";
  if (!form.course) errors.course = "Choose a course";
  if (form.password.length < minPassword) errors.password = `Use at least ${minPassword} characters`;
  if (confirm !== form.password) errors.confirm = "The passwords don't match";
  if (!form.consent) errors.consent = "Please agree to be contacted so a counsellor can reach you";
  return errors;
}

const Hint: React.FC<{ id: string; text?: string }> = ({ id, text }) =>
  text ? <p id={id} className="mt-1 text-xs text-danger">{text}</p> : null;

/** Student self-registration. On success the student is logged in; a taken email offers the Log in tab instead. */
export const RegisterForm: React.FC<{ onRegistered: (user: User) => void; onLogin: (email: string) => void }> = ({ onRegistered, onLogin }) => {
  const { register } = useAuth();
  const options = useApi<RegisterOptions>("/crm/auth/register/options");
  const [form, setForm] = useState<Registration>({
    first_name: "", last_name: "", email: "", country_code: "+91", phone: "", state: "", city: "",
    course: "", lateral_entry: false, password: "", consent: false,
  });
  const [confirm, setConfirm] = useState("");
  const [touched, setTouched] = useState<Partial<Record<Field, boolean>>>({});
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ text: string; taken: boolean } | null>(null);

  const minPassword = options.data?.min_password ?? 8;
  const errors = validate(form, confirm, minPassword);
  const shown = (f: Field) => (submitted || touched[f] ? errors[f] : undefined);
  const set = <K extends keyof Registration>(key: K, value: Registration[K]) => setForm((now) => ({ ...now, [key]: value }));
  const blur = (f: Field) => () => setTouched((now) => ({ ...now, [f]: true }));
  const a11y = (f: Field) => ({ "aria-invalid": Boolean(shown(f)), "aria-describedby": shown(f) ? `${f}-error` : undefined });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitted(true);
    setError(null);
    if (Object.keys(errors).length > 0) return;
    setBusy(true);
    try {
      const user = await register({ ...form, email: form.email.trim(), phone: form.phone.replace(/[\s-]/g, "") });
      onRegistered(user);
    } catch (err) {
      setError({ text: errorMessage(err), taken: err instanceof ApiError && err.status === 409 });
      setBusy(false);
    }
  }

  if (options.loading && !options.data) return <Loading label="Loading the form…" />;
  if (!options.data) return <ErrorBanner message={options.error ?? "Couldn't load the form"} onRetry={() => void options.reload()} />;
  const { states, courses, country_codes } = options.data;

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="reg-first" className="field-label">First name*</label>
          <input id="reg-first" autoComplete="given-name" value={form.first_name} onChange={(e) => set("first_name", e.target.value)}
            onBlur={blur("first_name")} className="field" {...a11y("first_name")} />
          <Hint id="first_name-error" text={shown("first_name")} />
        </div>
        <div>
          <label htmlFor="reg-last" className="field-label">Last name*</label>
          <input id="reg-last" autoComplete="family-name" value={form.last_name} onChange={(e) => set("last_name", e.target.value)}
            onBlur={blur("last_name")} className="field" {...a11y("last_name")} />
          <Hint id="last_name-error" text={shown("last_name")} />
        </div>
      </div>

      <div>
        <label htmlFor="reg-email" className="field-label">Email*</label>
        <input id="reg-email" type="email" autoComplete="email" value={form.email} onChange={(e) => set("email", e.target.value)}
          onBlur={blur("email")} className="field" {...a11y("email")} />
        <Hint id="email-error" text={shown("email")} />
      </div>

      <div>
        <label htmlFor="reg-phone" className="field-label">Mobile*</label>
        <div className="flex gap-2">
          <label htmlFor="reg-code" className="sr-only">Country code</label>
          <select id="reg-code" value={form.country_code} onChange={(e) => set("country_code", e.target.value)} className="field w-24 shrink-0">
            {country_codes.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <input id="reg-phone" type="tel" inputMode="numeric" autoComplete="tel-national" maxLength={12} value={form.phone}
            onChange={(e) => set("phone", e.target.value)} onBlur={blur("phone")} className="field flex-1 min-w-0 tabular-nums" {...a11y("phone")} />
        </div>
        <Hint id="phone-error" text={shown("phone")} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="reg-state" className="field-label">State*</label>
          <select id="reg-state" value={form.state} onChange={(e) => set("state", e.target.value)} onBlur={blur("state")}
            className="field" {...a11y("state")}>
            <option value="">Select a state</option>
            {states.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <Hint id="state-error" text={shown("state")} />
        </div>
        <div>
          <label htmlFor="reg-city" className="field-label">City*</label>
          <input id="reg-city" autoComplete="address-level2" value={form.city} onChange={(e) => set("city", e.target.value)}
            onBlur={blur("city")} className="field" {...a11y("city")} />
          <Hint id="city-error" text={shown("city")} />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-[1fr_140px] gap-4">
        <div>
          <label htmlFor="reg-course" className="field-label">Course*</label>
          <select id="reg-course" value={form.course} onChange={(e) => set("course", e.target.value)} onBlur={blur("course")}
            className="field" {...a11y("course")}>
            <option value="">Select a course</option>
            {courses.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <Hint id="course-error" text={shown("course")} />
        </div>
        <div>
          <label htmlFor="reg-lateral" className="field-label">Lateral entry</label>
          <select id="reg-lateral" value={form.lateral_entry ? "yes" : "no"} onChange={(e) => set("lateral_entry", e.target.value === "yes")} className="field">
            <option value="no">No</option>
            <option value="yes">Yes</option>
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label htmlFor="reg-password" className="field-label">Password*</label>
          <input id="reg-password" type="password" autoComplete="new-password" value={form.password}
            onChange={(e) => set("password", e.target.value)} onBlur={blur("password")} className="field" {...a11y("password")} />
          <Hint id="password-error" text={shown("password")} />
        </div>
        <div>
          <label htmlFor="reg-confirm" className="field-label">Confirm password*</label>
          <input id="reg-confirm" type="password" autoComplete="new-password" value={confirm}
            onChange={(e) => setConfirm(e.target.value)} onBlur={blur("confirm")} className="field" {...a11y("confirm")} />
          <Hint id="confirm-error" text={shown("confirm")} />
        </div>
      </div>

      <div>
        <label className="flex items-start gap-2.5 text-sm text-ink-secondary">
          <input type="checkbox" checked={form.consent} onChange={(e) => set("consent", e.target.checked)} onBlur={blur("consent")}
            className="mt-0.5 w-4 h-4 shrink-0 rounded accent-navy focus:outline-none focus-visible:ring-2 focus-visible:ring-navy focus-visible:ring-offset-1"
            {...a11y("consent")} />
          <span>{CONSENT_TEXT}*</span>
        </label>
        <Hint id="consent-error" text={shown("consent")} />
      </div>

      {error && (
        <div className="space-y-2">
          <ErrorBanner message={error.text} />
          {error.taken && (
            <button type="button" onClick={() => onLogin(form.email.trim())}
              className="text-sm font-medium text-navy underline underline-offset-2 hover:text-navy-hover rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-navy">
              Go to Log in with this email
            </button>
          )}
        </div>
      )}
      <Button type="submit" busy={busy} className="w-full">Register</Button>
      <p className="text-sm text-ink-secondary text-center">
        Already registered?{" "}
        <button type="button" onClick={() => onLogin(form.email.trim())}
          className="font-medium text-navy underline underline-offset-2 hover:text-navy-hover rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-navy">
          Log in
        </button>
      </p>
    </form>
  );
};
