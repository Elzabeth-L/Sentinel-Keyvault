import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const variants = cva(
  "inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-semibold transition focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50",
  {
    variants: {
      variant: {
        primary: "bg-primary text-slate-950 hover:bg-sky-300",
        secondary: "border border-border bg-slate-900/60 text-white hover:bg-slate-800",
        ghost: "text-muted hover:bg-slate-800/70 hover:text-white"
      }
    },
    defaultVariants: { variant: "primary" }
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof variants> {}

export function Button({ className, variant, ...props }: ButtonProps) {
  return <button className={cn(variants({ variant }), className)} {...props} />;
}

