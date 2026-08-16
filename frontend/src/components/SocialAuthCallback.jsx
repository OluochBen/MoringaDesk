import React, { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Loader2, AlertCircle, CheckCircle2 } from "lucide-react";

import { authApi } from "../services/api";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";

export function SocialAuthCallback({ onComplete }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [status, setStatus] = useState("pending"); // pending | success | error
  const [message, setMessage] = useState("");

  const params = useMemo(() => new URLSearchParams(location.search), [location.search]);

  useEffect(() => {
    const errorParam = params.get("error");
    const code = params.get("code");

    if (errorParam) {
      setStatus("error");
      setMessage(decodeURIComponent(errorParam));
      return;
    }

    if (!code) {
      setStatus("error");
      setMessage("Missing sign-in exchange code. Please try signing in again.");
      return;
    }

    (async () => {
      try {
        const result = await authApi.exchangeOAuthCode(code);
        const user = result.user;
        setStatus("success");
        setMessage(`You're in! Redirecting to your ${user.role} workspace.`);

        if (onComplete) {
          onComplete(user);
        } else {
          navigate(user.role === "admin" ? "/admin" : "/dashboard", { replace: true });
        }
      } catch (err) {
        console.error("Failed to complete social login", err);
        localStorage.removeItem("access_token");
        setStatus("error");
        setMessage(
          err.response?.data?.message ||
            err.response?.data?.error ||
            err.message ||
            "Unable to complete social sign-in. Please try again."
        );
      }
    })();
  }, [navigate, onComplete, params]);

  const handleBackToLogin = () => {
    navigate("/login", { replace: true });
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-green-50 to-blue-50 flex items-center justify-center px-4 py-10">
      <Card className="max-w-md w-full border border-emerald-100 bg-white shadow-xl shadow-emerald-100/40">
        <CardContent className="py-10 px-8 text-center space-y-4">
          {status === "pending" && (
            <>
              <Loader2 className="mx-auto h-10 w-10 animate-spin text-emerald-600" />
              <h2 className="text-xl font-semibold text-slate-900">Completing sign-in…</h2>
              <p className="text-sm text-muted-foreground">
                Hold on while we finish connecting your {providerFriendlyName(params.get("provider"))} account.
              </p>
            </>
          )}

          {status === "success" && (
            <>
              <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-600" />
              <h2 className="text-xl font-semibold text-slate-900">Sign-in complete!</h2>
              <p className="text-sm text-muted-foreground">{message}</p>
            </>
          )}

          {status === "error" && (
            <>
              <AlertCircle className="mx-auto h-10 w-10 text-red-500" />
              <h2 className="text-xl font-semibold text-slate-900">We couldn’t finish signing you in</h2>
              <p className="text-sm text-muted-foreground">{message}</p>
              <Button
                type="button"
                variant="outline"
                className="mt-2 w-full rounded-full border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                onClick={handleBackToLogin}
              >
                Return to login
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function providerFriendlyName(raw) {
  if (!raw) return "account";
  const normalized = raw.toLowerCase();
  if (normalized === "google") return "Google";
  if (normalized === "github") return "GitHub";
  if (normalized === "facebook") return "Facebook";
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}

export default SocialAuthCallback;
