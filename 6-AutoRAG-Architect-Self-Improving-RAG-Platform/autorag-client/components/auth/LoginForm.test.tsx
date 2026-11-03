import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import { LoginForm } from "@/components/auth/LoginForm";

const mockPush = vi.fn();
const mockRefresh = vi.fn();
const mockSignIn = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, refresh: mockRefresh }),
}));

vi.mock("@/lib/supabase", () => ({
  createSupabaseClient: () => ({
    auth: { signInWithPassword: mockSignIn },
  }),
}));

describe("LoginForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders email field, password field, and sign in button", () => {
    render(<LoginForm />);
    expect(screen.getByLabelText("Email address")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("submit button is disabled when fields are empty", () => {
    // The form pre-fills demo credentials by default (frictionless local
    // demo login) -- clear them to exercise the actual empty-fields state.
    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "" } });
    expect(screen.getByRole("button", { name: /sign in/i })).toBeDisabled();
  });

  it("submit button enables once email and password are filled", () => {
    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "user@company.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "mypassword" },
    });
    expect(screen.getByRole("button", { name: /sign in/i })).toBeEnabled();
  });

  it("shows invalid_credentials error when Supabase returns wrong password", async () => {
    mockSignIn.mockResolvedValueOnce({
      data: null,
      error: { message: "Invalid login credentials" },
    });

    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "user@company.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "wrongpassword" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Incorrect email or password.",
      );
    });
  });

  it("shows email_not_confirmed error", async () => {
    mockSignIn.mockResolvedValueOnce({
      data: null,
      error: { message: "Email not confirmed" },
    });

    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "unconfirmed@company.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "somepassword" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Please confirm your email before logging in.",
      );
    });
  });

  it("redirects to /dashboard on successful login", async () => {
    mockSignIn.mockResolvedValueOnce({ data: { user: { id: "abc" } }, error: null });

    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "user@company.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "correctpassword" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("does not redirect on error", async () => {
    mockSignIn.mockResolvedValueOnce({
      data: null,
      error: { message: "Invalid login credentials" },
    });

    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "user@company.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "badpassword" },
    });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });

    expect(mockPush).not.toHaveBeenCalled();
  });

  it("shows forgot password and create account links", () => {
    render(<LoginForm />);
    expect(screen.getByRole("link", { name: /forgot password/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /request access/i })).toBeInTheDocument();
  });
});
