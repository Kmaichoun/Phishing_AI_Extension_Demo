import { Icon } from './Icon';
import { useTheme } from '../contexts/ThemeContext';

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const dark = theme === 'dark';
  return (
    <button
      className="theme-toggle"
      type="button"
      onClick={toggleTheme}
      aria-label={dark ? 'เปลี่ยนเป็นโหมดสว่าง' : 'เปลี่ยนเป็นโหมดมืด'}
      aria-pressed={dark}
    >
      <span className="theme-icon-wrap" data-theme-icon aria-hidden="true">
        <Icon name="sun" className="ui-icon theme-icon-sun" />
        <Icon name="moon" className="ui-icon theme-icon-moon" />
      </span>
      <span data-theme-label>{dark ? 'Light' : 'Dark'}</span>
    </button>
  );
}
