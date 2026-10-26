import React from 'react'
import { motion, useReducedMotion } from 'motion/react'

interface ButtonProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'onAnimationStart' | 'onAnimationEnd' | 'onAnimationIteration'> {
  variant?: 'primary' | 'secondary' | 'coral' | 'ghost' | 'blue' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  disabledTooltip?: string
  loading?: boolean
}

export const Button: React.FC<ButtonProps> = ({ children, variant = 'primary', size = 'md', disabledTooltip, disabled = false, loading = false, className = '', ...props }) => {
  const reducedMotion = useReducedMotion()
  const sizes = { sm: 'px-4 py-2 text-[13px]', md: 'px-5 py-2.5 text-[15px]', lg: 'px-6 py-3 text-[17px]' }
  const styles = {
    primary: 'bg-apple-blue text-white hover:bg-apple-blue-hover',
    blue: 'bg-apple-blue text-white hover:bg-apple-blue-hover',
    coral: 'bg-apple-blue text-white hover:bg-apple-blue-hover',
    secondary: 'border border-text-primary bg-transparent text-text-primary hover:bg-text-primary hover:text-white',
    ghost: 'bg-ash text-text-primary hover:bg-[#dcdce1]',
    danger: 'border border-danger-red/40 bg-transparent text-danger-red hover:bg-danger-subtle',
  }
  const isInactive = disabled || loading
  const content = <motion.span className="inline-flex" whileHover={isInactive || reducedMotion ? undefined : { y: -1 }} whileTap={isInactive || reducedMotion ? undefined : { scale: .98 }} transition={{ type: 'spring', stiffness: 520, damping: 28 }}><button {...props} disabled={isInactive} className={`inline-flex items-center justify-center gap-2 rounded-full font-medium tracking-[-.015em] transition-colors duration-150 ${sizes[size]} ${styles[variant]} ${isInactive ? 'cursor-not-allowed opacity-45' : ''} ${className}`}>
    {loading && <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />}
    {children}
  </button></motion.span>
  return disabled && disabledTooltip ? <span className="group relative inline-flex">{content}<span className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 hidden w-max max-w-xs -translate-x-1/2 rounded-full bg-text-primary px-3 py-1.5 text-[12px] text-white group-hover:block">{disabledTooltip}</span></span> : content
}
