import { cn } from "@/lib/utils";

// Skeleton placeholder for loading states. A muted, pulsing block sized by the
// caller via className -- the dashboard's standard for cold loads (replacing
// spinners), so a revisit shows the shape of the content while it revalidates.
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  );
}

export { Skeleton };
