interface CardProps extends React.HTMLAttributes<HTMLDivElement> {}

function Card({ className = "", ...props }: CardProps) {
  return (
    <div
      className={`rounded-md border border-zinc-200 bg-white text-zinc-900 ${className}`}
      {...props}
    />
  );
}

interface CardHeaderProps extends React.HTMLAttributes<HTMLDivElement> {}

function CardHeader({ className = "", ...props }: CardHeaderProps) {
  return (
    <div
      className={`flex flex-col space-y-1.5 p-4 ${className}`}
      {...props}
    />
  );
}

interface CardTitleProps extends React.HTMLAttributes<HTMLHeadingElement> {}

function CardTitle({ className = "", ...props }: CardTitleProps) {
  return (
    <h3
      className={`text-lg font-semibold leading-none tracking-tight ${className}`}
      {...props}
    />
  );
}

interface CardContentProps extends React.HTMLAttributes<HTMLDivElement> {}

function CardContent({ className = "", ...props }: CardContentProps) {
  return <div className={`p-4 pt-0 ${className}`} {...props} />;
}

export { Card, CardHeader, CardTitle, CardContent };