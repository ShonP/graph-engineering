// fixes #1234 - an issue ref in a comment is not a colour
/* see #1234 and #abc */
import { cn } from '@/lib/cn';
import { TextInput } from '@/components/text-input';

export const Button = ({ className }: { className?: string }) => (
  <div className="border-collapse border-t-bg border-x-danger border-bs-fg ring-2 ring-offset-2 ring-offset-bg">
    <a href="#add" className="placeholder-shown:bg-muted text-body text-center bg-fg/50 hover:bg-accent!">
      &#123;
    </a>
    <input data-testid="text-input" id="bg-picker" className="border-2 border-border outline-hidden outline-offset-2 focus-visible:outline-accent" />
    <p className={cn('text-fg text-caption shadow-md shadow-card divide-y divide-border', className)} />
    <p className="bg-linear-to-r from-accent from-10% via-bg to-danger bg-clip-text text-transparent" />
    <p className="bg-[url(/hero.png)] text-[14px] bg-(--color-bg) bg-[var(--color-bg)] bg-no-repeat bg-cover" />
    <p className="text-shadow-sm drop-shadow-lg inset-shadow-xs decoration-wavy fill-none stroke-2 text-inherit border-current" />
    <p className="text-wrap text-ellipsis border-spacing-2 border-separate border-solid ring-inset" style={{ width: 4 }} />
    <p style={{ borderColor: 'var(--color-border)' }} className="transition-[color,border-color]" />
    <TextInput />
  </div>
);
