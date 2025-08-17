"use client"

import { useState, useEffect } from "react"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { ElevatorStatus } from "@/lib/types/elevator"
import { cn } from "@/lib/utils"

interface ElevatorShaftProps {
  elevators: ElevatorStatus[]
  totalFloors: number
  onFloorClick?: (floor: number) => void
}

export function ElevatorShaft({ elevators, totalFloors, onFloorClick }: ElevatorShaftProps) {
  const [animatingElevators, setAnimatingElevators] = useState<Set<number>>(new Set())
  const [previousPositions, setPreviousPositions] = useState<Map<number, number>>(new Map())

  useEffect(() => {
    elevators.forEach((elevator) => {
      const prevFloor = previousPositions.get(elevator.id)
      if (prevFloor !== undefined && prevFloor !== elevator.current_floor) {
        setAnimatingElevators((prev) => new Set([...prev, elevator.id]))
        setTimeout(() => {
          setAnimatingElevators((prev) => {
            const newSet = new Set(prev)
            newSet.delete(elevator.id)
            return newSet
          })
        }, 1000)
      }
    })

    const newPositions = new Map()
    elevators.forEach((elevator) => {
      newPositions.set(elevator.id, elevator.current_floor)
    })
    setPreviousPositions(newPositions)
  }, [elevators])

  // Calculate elevator position based on floor
  const getElevatorPosition = (floor: number) => {
    const floorHeight = 60 // Height per floor in pixels
    return (totalFloors - floor) * floorHeight
  }

  // Get elevator status color
  const getStatusColor = (state: ElevatorStatus["state"]) => {
    switch (state) {
      case "idle":
        return "bg-emerald-500 shadow-emerald-500/50"
      case "moving":
        return "bg-blue-500 shadow-blue-500/50 animate-pulse"
      case "doors_open":
        return "bg-amber-500 shadow-amber-500/50"
      case "maintenance":
        return "bg-orange-500 shadow-orange-500/50"
      case "emergency":
        return "bg-red-500 shadow-red-500/50 animate-pulse"
      default:
        return "bg-gray-500"
    }
  }

  const getDirectionArrow = (direction: ElevatorStatus["direction"], state: ElevatorStatus["state"]) => {
    const baseClass = "text-lg transition-all duration-300"
    switch (direction) {
      case "up":
        return <span className={cn(baseClass, state === "moving" && "animate-bounce")}>⬆️</span>
      case "down":
        return <span className={cn(baseClass, state === "moving" && "animate-bounce")}>⬇️</span>
      default:
        return <span className={baseClass}>🟢</span>
    }
  }

  const getElevatorIcon = (state: ElevatorStatus["state"]) => {
    switch (state) {
      case "doors_open":
        return "🚪"
      case "maintenance":
        return "🔧"
      case "emergency":
        return "🚨"
      default:
        return "🏢"
    }
  }

  return (
    <div className="flex gap-6">
      {/* Floor Numbers */}
      <div className="flex flex-col-reverse gap-0">
        {Array.from({ length: totalFloors }, (_, i) => i + 1).map((floor) => (
          <div
            key={floor}
            className={cn(
              "h-15 flex items-center justify-center w-12 border-r border-border cursor-pointer transition-all duration-200",
              "text-sm font-medium hover:bg-primary/10 hover:text-primary hover:scale-105",
              "relative group",
            )}
            onClick={() => onFloorClick?.(floor)}
          >
            <span className="relative z-10">{floor}</span>
            <div className="absolute inset-0 bg-primary/5 opacity-0 group-hover:opacity-100 transition-opacity duration-200 rounded-l" />
          </div>
        ))}
      </div>

      {/* Elevator Shafts */}
      {elevators.map((elevator) => (
        <div key={elevator.id} className="relative">
          {/* Shaft Background */}
          <div className="w-20 bg-card border border-border rounded-lg overflow-hidden shadow-lg">
            <div
              className="relative bg-gradient-to-b from-muted/20 to-muted/40"
              style={{ height: `${totalFloors * 60}px` }}
            >
              {Array.from({ length: totalFloors - 1 }, (_, i) => (
                <div
                  key={i}
                  className="absolute w-full border-t border-border/60"
                  style={{ bottom: `${(i + 1) * 60}px` }}
                />
              ))}

              <div
                className={cn(
                  "absolute w-16 h-12 mx-2 rounded-md flex flex-col items-center justify-center text-white font-bold transition-all duration-1000 ease-in-out shadow-lg",
                  getStatusColor(elevator.state),
                  animatingElevators.has(elevator.id) && "scale-110",
                  elevator.state === "moving" && "shadow-2xl",
                )}
                style={{
                  bottom: `${getElevatorPosition(elevator.current_floor)}px`,
                }}
              >
                <div className="text-center space-y-0.5">
                  <div className="text-xs flex items-center justify-center">
                    {getDirectionArrow(elevator.direction, elevator.state)}
                  </div>
                  <div className="text-xs font-bold">E{elevator.id}</div>
                </div>

                <div className="absolute -top-1 -right-1 text-xs">{getElevatorIcon(elevator.state)}</div>
              </div>

              {elevator.destination_floor && elevator.destination_floor !== elevator.current_floor && (
                <div
                  className="absolute w-16 h-2 mx-2 bg-gradient-to-r from-accent to-accent/60 rounded-full opacity-80 animate-pulse shadow-lg"
                  style={{
                    bottom: `${getElevatorPosition(elevator.destination_floor) + 22}px`,
                  }}
                >
                  <div className="absolute inset-0 bg-accent rounded-full animate-ping opacity-30" />
                </div>
              )}

              {elevator.state === "moving" && elevator.destination_floor && (
                <div
                  className="absolute w-1 bg-gradient-to-b from-primary/60 to-transparent rounded-full mx-9.5 opacity-60"
                  style={{
                    bottom: `${Math.min(getElevatorPosition(elevator.current_floor), getElevatorPosition(elevator.destination_floor))}px`,
                    height: `${Math.abs(getElevatorPosition(elevator.destination_floor) - getElevatorPosition(elevator.current_floor))}px`,
                  }}
                />
              )}
            </div>
          </div>

          <Card className="mt-4 p-3 w-20 shadow-md hover:shadow-lg transition-shadow duration-200">
            <div className="text-center space-y-2">
              <div className="font-bold text-sm flex items-center justify-center gap-1">🏢 E{elevator.id}</div>
              <Badge
                variant={elevator.state === "idle" ? "secondary" : "default"}
                className={cn("text-xs transition-all duration-200", elevator.state === "moving" && "animate-pulse")}
              >
                {elevator.state.replace("_", " ")}
              </Badge>
              <div className="text-xs text-muted-foreground font-medium">Floor {elevator.current_floor}</div>
              {elevator.destination_floor && (
                <div className="text-xs text-accent-foreground font-bold animate-pulse">
                  🎯 → {elevator.destination_floor}
                </div>
              )}
            </div>
          </Card>
        </div>
      ))}
    </div>
  )
}
