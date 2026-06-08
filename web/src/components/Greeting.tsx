function greetingByHour(): string {
  const h = new Date().getHours();
  if (h < 12) return "Bom dia";
  if (h < 18) return "Boa tarde";
  return "Boa noite";
}

interface Props {
  username: string | null;
}

export function Greeting({ username }: Props) {
  return (
    <div className="greeting">
      <div className="orb" aria-hidden />
      <h1 className="greeting-title">
        {greetingByHour()}{username ? `, ${username}` : ""}!
        <br />
        Posso te ajudar com algo?
      </h1>
      <p className="greeting-subtitle">
        Escolha uma sugestão abaixo ou escreva a sua para começar a conversar com o ThinkAI
      </p>
    </div>
  );
}
