import React, { useRef } from 'react'
import { motion, useMotionValue, useSpring, useReducedMotion } from 'motion/react'
import { spring } from '../../design/motion'

interface MagneticProps {
  children: React.ReactNode
  strength?: number
  className?: string
  disabled?: boolean
}

export const Magnetic: React.FC<MagneticProps> = ({
  children,
  strength = 8,
  className = '',
  disabled = false,
}) => {
  const ref = useRef<HTMLDivElement>(null)
  const reducedMotion = useReducedMotion()

  const x = useMotionValue(0)
  const y = useMotionValue(0)

  const smoothX = useSpring(x, { stiffness: 350, damping: 25, mass: 0.5 })
  const smoothY = useSpring(y, { stiffness: 350, damping: 25, mass: 0.5 })

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (disabled || reducedMotion || !ref.current) return
    const rect = ref.current.getBoundingClientRect()
    const centerX = rect.left + rect.width / 2
    const centerY = rect.top + rect.height / 2
    const distanceX = e.clientX - centerX
    const distanceY = e.clientY - centerY

    // Scale displacement proportionally, max strength
    const factorX = (distanceX / (rect.width / 2)) * strength
    const factorY = (distanceY / (rect.height / 2)) * strength
    x.set(Math.max(-strength, Math.min(strength, factorX)))
    y.set(Math.max(-strength, Math.min(strength, factorY)))
  }

  const handleMouseLeave = () => {
    x.set(0)
    y.set(0)
  }

  if (reducedMotion || disabled) {
    return <div className={`inline-block ${className}`}>{children}</div>
  }

  return (
    <motion.div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{ x: smoothX, y: smoothY }}
      whileTap={{ scale: 0.97 }}
      transition={spring.snappy}
      className={`inline-block ${className}`}
    >
      {children}
    </motion.div>
  )
}
