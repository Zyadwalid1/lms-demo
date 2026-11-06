import { Monitor, Moon, Sun } from 'lucide-react'

import { cn } from '@/lib/cn'
import { type ThemeChoice, useTheme } from '@/lib/theme'

import { Button } from './button'
import { Menu, MenuContent, MenuRadioGroup, MenuRadioItem, MenuTrigger } from './menu'

const options: { value: ThemeChoice; label: string; Icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', Icon: Sun },
  { value: 'dark', label: 'Dark', Icon: Moon },
  { value: 'system', label: 'Match my computer', Icon: Monitor },
]

export function ThemeToggle({ className, onDark }: { className?: string; onDark?: boolean }) {
  const { choice, dark, setChoice } = useTheme()
  return (
    <Menu>
      <MenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Theme" className={cn(onDark && 'text-nav-text hover:bg-nav-hover hover:text-white', className)}>
          {dark ? <Moon /> : <Sun />}
        </Button>
      </MenuTrigger>
      <MenuContent>
        <MenuRadioGroup value={choice} onValueChange={(v) => setChoice(v as ThemeChoice)}>
          {options.map(({ value, label, Icon }) => (
            <MenuRadioItem key={value} value={value}>
              <Icon /> {label}
            </MenuRadioItem>
          ))}
        </MenuRadioGroup>
      </MenuContent>
    </Menu>
  )
}
