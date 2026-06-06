/** Saudação dependente do horário, exibida no estado inicial (tela vazia). */
function greetingByHour(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export function Greeting() {
  return (
    <div className="greeting">
      <div className="orb" aria-hidden />
      <h1 className="greeting-title">
        {greetingByHour()}, Milovan
        <br />
        Can I help you with anything?
      </h1>
      <p className="greeting-subtitle">
        Choose a prompt below or write your own to start chatting with ThinkAI
      </p>
    </div>
  );
}
