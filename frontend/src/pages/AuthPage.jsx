import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/App";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Shield, MapPin } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";

export default function AuthPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [loginForm, setLoginForm] = useState({ email: "", password: "" });
  const [registerForm, setRegisterForm] = useState({ name: "", email: "", password: "" });

  useEffect(() => {
    if (user) navigate("/", { replace: true });
  }, [user, navigate]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.login(loginForm.email, loginForm.password);
      login(res.token, res.user);
      toast.success("Willkommen zurueck!");
      navigate("/");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Login fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.register(registerForm.name, registerForm.email, registerForm.password);
      login(res.token, res.user);
      toast.success("Konto erstellt!");
      navigate("/");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Registrierung fehlgeschlagen");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-split" data-testid="auth-page">
      <div className="flex items-center justify-center p-8 md:p-12">
        <div className="w-full max-w-md space-y-8">
          <div className="space-y-2">
            <div className="flex items-center gap-3 mb-6">
              <div className="h-10 w-10 rounded-xl bg-primary/10 flex items-center justify-center">
                <Shield className="h-5 w-5 text-primary" />
              </div>
              <span className="text-xl font-bold font-['Barlow'] tracking-tight text-foreground">SafeSteps Bern</span>
            </div>
            <h1 className="text-3xl font-bold font-['Barlow'] tracking-tight text-foreground">
              Sichere Schulwege finden
            </h1>
            <p className="text-muted-foreground text-sm">
              Berechne den sichersten Schulweg fuer dein Kind in Bern.
            </p>
          </div>

          <Tabs defaultValue="login" className="w-full">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="login" data-testid="login-tab">Anmelden</TabsTrigger>
              <TabsTrigger value="register" data-testid="register-tab">Registrieren</TabsTrigger>
            </TabsList>

            <TabsContent value="login" className="space-y-4 mt-6">
              <form onSubmit={handleLogin} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="login-email">E-Mail</Label>
                  <Input
                    id="login-email"
                    data-testid="login-email-input"
                    type="email"
                    placeholder="name@example.com"
                    value={loginForm.email}
                    onChange={(e) => setLoginForm({ ...loginForm, email: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="login-password">Passwort</Label>
                  <Input
                    id="login-password"
                    data-testid="login-password-input"
                    type="password"
                    placeholder="Passwort eingeben"
                    value={loginForm.password}
                    onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
                    required
                  />
                </div>
                <Button type="submit" data-testid="login-submit-btn" className="w-full" disabled={loading}>
                  {loading ? "Wird geladen..." : "Anmelden"}
                </Button>
              </form>
            </TabsContent>

            <TabsContent value="register" className="space-y-4 mt-6">
              <form onSubmit={handleRegister} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="reg-name">Name</Label>
                  <Input
                    id="reg-name"
                    data-testid="register-name-input"
                    type="text"
                    placeholder="Dein Name"
                    value={registerForm.name}
                    onChange={(e) => setRegisterForm({ ...registerForm, name: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="reg-email">E-Mail</Label>
                  <Input
                    id="reg-email"
                    data-testid="register-email-input"
                    type="email"
                    placeholder="name@example.com"
                    value={registerForm.email}
                    onChange={(e) => setRegisterForm({ ...registerForm, email: e.target.value })}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="reg-password">Passwort</Label>
                  <Input
                    id="reg-password"
                    data-testid="register-password-input"
                    type="password"
                    placeholder="Mindestens 6 Zeichen"
                    value={registerForm.password}
                    onChange={(e) => setRegisterForm({ ...registerForm, password: e.target.value })}
                    required
                  />
                </div>
                <Button type="submit" data-testid="register-submit-btn" className="w-full" disabled={loading}>
                  {loading ? "Wird erstellt..." : "Konto erstellen"}
                </Button>
              </form>
            </TabsContent>
          </Tabs>

          <p className="text-xs text-muted-foreground text-center pt-4">
            <MapPin className="inline h-3 w-3 mr-1" />
            SafeSteps Bern - Prototyp / Demo-Version
          </p>
        </div>
      </div>

      <div
        className="auth-image"
        style={{
          backgroundImage: `url(https://images.unsplash.com/photo-1675422409769-26556c0eb312?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzNTl8MHwxfHNlYXJjaHw0fHxCZXJuJTIwU3dpdHplcmxhbmQlMjBjaXR5JTIwYWVyaWFsJTIwdmlldyUyMHJpdmVyJTIwQWFyZXxlbnwwfHx8fDE3NzI0NjEwNDZ8MA&ixlib=rb-4.1.0&q=85)`,
        }}
      >
        <div className="absolute inset-0 flex items-end p-10 z-10">
          <div className="text-white">
            <h2 className="text-3xl font-bold font-['Barlow'] mb-2">Bern, Schweiz</h2>
            <p className="text-white/80 text-sm">
              Sichere Schulwege mit Echtzeit-Umweltdaten
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
