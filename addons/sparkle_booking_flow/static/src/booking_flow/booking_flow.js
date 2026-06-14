/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { mountComponent } from "@web/env";
import { rpc } from "@web/core/network/rpc";
import rootWidget from "root.widget";

const MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
];

function formatDate(date) {
    const year = date.getFullYear();
    const month = `${date.getMonth() + 1}`.padStart(2, "0");
    const day = `${date.getDate()}`.padStart(2, "0");
    return `${year}-${month}-${day}`;
}

function parseDate(value) {
    const [year, month, day] = value.split("-").map((part) => parseInt(part, 10));
    return new Date(year, month - 1, day);
}

function formatDateLabel(value) {
    const date = parseDate(value);
    return `${date.getDate()} ${MONTH_NAMES[date.getMonth()].toUpperCase()}, ${date.getFullYear()}`;
}

function startOfToday() {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

function buildMonthDays(year, month) {
    const today = startOfToday();
    const first = new Date(year, month, 1);
    const firstGridDate = new Date(year, month, 1 - first.getDay());
    const days = [];
    for (let index = 0; index < 42; index++) {
        const date = new Date(firstGridDate);
        date.setDate(firstGridDate.getDate() + index);
        days.push({
            key: formatDate(date),
            label: `${date.getDate()}`.padStart(2, "0"),
            value: formatDate(date),
            isMuted: date.getMonth() !== month,
            isPast: date < today,
            isWeekend: date.getDay() === 0 || date.getDay() === 6,
        });
    }
    return days;
}

function buildBookingStart(dateValue, timeValue) {
    const match = timeValue.match(/^(\d{2}):(\d{2}) (AM|PM)$/);
    if (!dateValue || !match) {
        return "";
    }
    let hours = parseInt(match[1], 10);
    const minutes = match[2];
    if (match[3] === "PM" && hours !== 12) {
        hours += 12;
    }
    if (match[3] === "AM" && hours === 12) {
        hours = 0;
    }
    return `${dateValue}T${`${hours}`.padStart(2, "0")}:${minutes}:00`;
}

class Summary extends Component {
    static template = "sparkle_booking_flow.Summary";
    static props = {
        selectedService: { optional: true },
        selectedDateLabel: { optional: true },
        selectedTime: { optional: true },
    };
}

export class SparkleBookingFlow extends Component {
    static template = "sparkle_booking_flow.SparkleBookingFlow";
    static components = { Summary };

    setup() {
        this.state = useState({
            isOpen: false,
            step: 1,
            services: [],
            selectedService: null,
            selectedDate: null,
            selectedDateLabel: "",
            selectedTime: null,
            customer: {
                name: "",
                email: "",
                phone: "",
                location: "",
                message: "",
            },
            paymentMethod: "pay_later",
            bookingId: null,
            loading: false,
            loadingSlots: false,
            error: null,
            currentYear: new Date().getFullYear(),
            currentMonth: new Date().getMonth(),
            times: [],
        });
        this.weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
        window.sparkleBookingFlow = this;

        onWillStart(async () => {
            await this.fetchServices();
        });
    }

    get progressWidth() {
        return `${(this.state.step / 5) * 100}%`;
    }

    get title() {
        return [
            "",
            "Select the Service You Need",
            "Schedule Your Booking",
            "Complete Your Details",
            "Confirm Your Payment",
            "Booking Confirmed",
        ][this.state.step];
    }

    get subtitle() {
        return [
            "",
            "Select a service to get started with expert support.",
            "Select a convenient date and time for your appointment.",
            "Enter your contact details to proceed with the booking.",
            "Proceed with payment to finalize your appointment.",
            "Your cleaning service has been successfully booked.",
        ][this.state.step];
    }

    get days() {
        return buildMonthDays(this.state.currentYear, this.state.currentMonth);
    }

    get currentMonthName() {
        return MONTH_NAMES[this.state.currentMonth].toUpperCase();
    }

    get canGoToPreviousMonth() {
        const today = startOfToday();
        return (
            this.state.currentYear > today.getFullYear() ||
            (this.state.currentYear === today.getFullYear() && this.state.currentMonth > today.getMonth())
        );
    }

    async fetchServices() {
        try {
            const services = await rpc("/sparkle-booking/services", {});
            this.state.services = services;
            if (!services.length) {
                this.state.error = "No cleaning services are available yet.";
            }
        } catch {
            this.state.error = "We could not load services. Please try again.";
        }
    }

    open() {
        this.fetchServices();
        this.state.isOpen = true;
        document.body.classList.add("o_sparkle_booking_locked");
    }

    close() {
        this.state.isOpen = false;
        document.body.classList.remove("o_sparkle_booking_locked");
    }

    reset() {
        this.state.step = 1;
        this.state.selectedService = null;
        this.state.selectedDate = null;
        this.state.selectedDateLabel = "";
        this.state.selectedTime = null;
        this.state.times = [];
        this.state.currentYear = new Date().getFullYear();
        this.state.currentMonth = new Date().getMonth();
        this.state.customer.name = "";
        this.state.customer.email = "";
        this.state.customer.phone = "";
        this.state.customer.location = "";
        this.state.customer.message = "";
        this.state.paymentMethod = "pay_later";
        this.state.bookingId = null;
        this.state.error = null;
    }

    back() {
        if (this.state.step <= 1) {
            this.close();
            return;
        }
        this.state.step -= 1;
        this.state.error = null;
    }

    async next() {
        this.state.error = null;
        if (this.state.step === 5) {
            window.location.href = "/";
            return;
        }
        if (!this.validateStep()) {
            return;
        }
        if (this.state.step === 4) {
            await this.submitBooking();
            return;
        }
        if (this.state.step < 5) {
            this.state.step += 1;
        }
    }

    validateStep() {
        if (this.state.step === 1 && !this.state.selectedService) {
            this.state.error = "Please select a service.";
            return false;
        }
        if (this.state.step === 2 && (!this.state.selectedDate || !this.state.selectedTime)) {
            this.state.error = "Please select a date and time.";
            return false;
        }
        if (this.state.step === 3) {
            const customer = this.state.customer;
            if (!customer.name.trim() || !customer.email.trim() || !customer.phone.trim()) {
                this.state.error = "Please enter your name, email, and phone.";
                return false;
            }
        }
        return true;
    }

    selectService(service) {
        this.state.selectedService = service;
        this.state.selectedDate = null;
        this.state.selectedDateLabel = "";
        this.state.selectedTime = null;
        this.state.times = [];
        this.state.error = null;
    }

    async selectDate(day) {
        if (day.isPast) {
            return;
        }
        this.state.selectedDate = day.value;
        this.state.selectedDateLabel = formatDateLabel(day.value);
        this.state.selectedTime = null;
        this.state.error = null;
        await this.fetchAvailability();
    }

    selectTime(time) {
        this.state.selectedTime = time;
        this.state.error = null;
    }

    goToPreviousMonth() {
        if (!this.canGoToPreviousMonth) {
            return;
        }
        this.changeMonth(-1);
    }

    goToNextMonth() {
        this.changeMonth(1);
    }

    changeMonth(delta) {
        const date = new Date(this.state.currentYear, this.state.currentMonth + delta, 1);
        this.state.currentYear = date.getFullYear();
        this.state.currentMonth = date.getMonth();
        this.state.selectedDate = null;
        this.state.selectedDateLabel = "";
        this.state.selectedTime = null;
        this.state.times = [];
        this.state.error = null;
    }

    async fetchAvailability() {
        if (!this.state.selectedService || !this.state.selectedDate) {
            this.state.times = [];
            return;
        }
        this.state.loadingSlots = true;
        try {
            const result = await rpc("/sparkle-booking/availability", {
                service_id: this.state.selectedService.id,
                date: this.state.selectedDate,
            });
            this.state.times = result.slots || [];
            if (!result.success) {
                this.state.error = result.message || "No times are available for this date.";
            } else if (!this.state.times.length) {
                this.state.error = "No times are available for this date.";
            }
        } catch {
            this.state.times = [];
            this.state.error = "We could not load available times. Please try again.";
        } finally {
            this.state.loadingSlots = false;
        }
    }

    updateCustomer(field, ev) {
        this.state.customer[field] = ev.target.value;
    }

    async submitBooking() {
        this.state.loading = true;
        try {
            const result = await rpc("/sparkle-booking/create", {
                service_id: this.state.selectedService.id,
                customer_name: this.state.customer.name,
                email: this.state.customer.email,
                phone: this.state.customer.phone,
                location: this.state.customer.location,
                message: this.state.customer.message,
                booking_start: buildBookingStart(this.state.selectedDate, this.state.selectedTime),
            });
            if (!result.success) {
                this.state.error = result.message || "We could not create this booking.";
                return;
            }
            this.state.bookingId = result.booking_id;
            this.state.step = 5;
        } catch {
            this.state.error = "We could not create this booking. Please try again.";
        } finally {
            this.state.loading = false;
        }
    }
}

function wireBookingButtons() {
    if (document.body.dataset.sparkleBookingClickBound) {
        return;
    }
    document.body.dataset.sparkleBookingClickBound = "1";
    document.addEventListener("click", async (ev) => {
        const trigger = ev.target.closest(".js_open_sparkle_booking");
        if (!trigger) {
            return;
        }
        ev.preventDefault();
        const flow = window.sparkleBookingFlow || (await mountSparkleBookingFlow());
        if (flow) {
            flow.open();
        }
    });
}

function isWebsiteEditorActive() {
    const searchParams = new URLSearchParams(window.location.search);
    return (
        searchParams.has("enable_editor") ||
        searchParams.has("edit_translations") ||
        document.body.classList.contains("editor_enable") ||
        document.documentElement.classList.contains("editor_enable") ||
        document.querySelector("#wrapwrap[data-wysiwyg='1'], #wrapwrap[data-wysiwyg='true']")
    );
}

async function mountSparkleBookingFlow() {
    if (isWebsiteEditorActive()) {
        return null;
    }
    let target = document.querySelector("#sparkle_booking_flow_mount");
    if (!target) {
        target = document.createElement("div");
        target.id = "sparkle_booking_flow_mount";
        document.body.appendChild(target);
    }
    if (!target) {
        return null;
    }
    if (target.dataset.sparkleBookingMounted && window.sparkleBookingFlow) {
        return window.sparkleBookingFlow;
    }
    if (target.dataset.sparkleBookingMounted && !window.sparkleBookingFlow) {
        delete target.dataset.sparkleBookingMounted;
    }
    target.dataset.sparkleBookingMounted = "1";
    try {
        const publicRoot = await rootWidget;
        await mountComponent(SparkleBookingFlow, target, { env: publicRoot.env });
        return window.sparkleBookingFlow;
    } catch (error) {
        delete target.dataset.sparkleBookingMounted;
        throw error;
    }
}

async function startSparkleBookingFlow() {
    wireBookingButtons();
    if (isWebsiteEditorActive()) {
        return;
    }
    await mountSparkleBookingFlow();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startSparkleBookingFlow);
} else {
    startSparkleBookingFlow();
}
