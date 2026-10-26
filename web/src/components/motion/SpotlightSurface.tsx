import React, { useRef, useState } from 'react'
import { motion, useMotionValue, useSpring, useMotionTemplate, useReducedMotion } from 'motion/react'

interface SpotlightSurfaceProps {
  children: React.ReactNode
  className?: string
  radius?: number
  disabled?: boolean
  onClick?: () => void
}

export const SpotlightSurface: React.FC<SpotlightSurfaceProps> = ({
  children,
  className = '',
  radius = 420,
  disabled = false,
  onClick,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isHovered, setIsHovered] = useState(false)
  const reducedMotion = useReducedMotion()

  const mouseX = useMotionValue(0)
  const mouseY = useMotionValue(0)

  const smoothX = useSpring(mouseX, { stiffness: 400, damping: 30 })
  const smoothY = useSpring(mouseY, { stiffness: 400, damping: 30 })

  const background = useMotionTemplate`radial-gradient(${radius}px circle at ${smoothX}px ${smoothY}px, var(--pearl-1), transparent 65%)`
  const borderBackground = useMotionTemplate`radial-gradient(${radius * 0.75}px circle at ${smoothX}px ${smoothY}px, var(--pearl-2), transparent 70%)`

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (reducedMotion || disabled || !containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    mouseX.set(e.clientX - rect.left)
    mouseY.set(e.clientY - rect.top)
  }

  if (reducedMotion || disabled) {
    return (
      <div className={`relative ${className}`} onClick={onClick}>
        {children}
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onMouseMove={handleMouseMove}
      onClick={onClick}
      className={`relative overflow-hidden group ${className}`}
    >
      {/* Background pearl light on hover */}
      <motion.div
        className="pointer-events-none absolute inset-0 z-0 transition-opacity duration-300"
        style={{
          background,
          opacity: isHovered ? 0.45 : 0,
        }}
      />

      {/* Border glow highlight */}
      <motion.div
        className="pointer-events-none absolute inset-0 z-0 rounded-[inherit] transition-opacity duration-300"
        style={{
          padding: '1px',
          background: borderBackground,
          opacity: isHovered ? 0.8 : 0,
          WebkitMask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
          WebkitMaskComposite: 'xor',
          maskComposite: 'exclude',
        }}
      />

      {/* Surface content */}
      <div className="relative z-10 w-full h-full">
        {children}
      </div>
    </div>
  )
}
