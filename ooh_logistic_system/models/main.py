from odoo import models, fields, api, _
from datetime import datetime
import logging
from random import randint

_logger = logging.getLogger(__name__)


# today = datetime.date.today()
class OpenFile(models.Model):
    _name = 'open.file'
    _description = "The file information and documents management"
    _inherit = ["mail.thread", 'mail.activity.mixin']

    def get_associated_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Invoices',
            'view_mode': 'tree',
            'res_model': 'account.move',
            'domain': [('file_ref', '=', self.name)],
            'context': "{'create': False}"
        }

    def get_associated_trips(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Trips',
            'view_mode': 'tree',
            'res_model': 'vehicle.trip',
            'domain': [('related_file.id', '=', self.id)],
            'context': "{'create': False}"
        }

    def compute_count(self):
        unpaid = 0.00
        invoices = self.env['account.move'].search(
            [('file_ref', '=', self.name)])
        for record in invoices:
            unpaid += record.amount_residual
        return self.sudo().write({'invoice_count': unpaid})

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'open.file') or _('New')
        res = super(OpenFile, self).create(vals)
        return res

    def calculate_account_blc(self):
        value = 0.00
        for x in self.file_lines:
            value += x.product_id.list_price
        self.account_total = value
        return True

    def action_draft(self):
        if self:
            self.sudo().write({"state": "draft"})

    def action_confirm(self):
        if self:
            self.sudo().write({"state": "confirm"})
    state = fields.Selection([
        ('draft', 'DRAFT'),
        ('confirm', 'CONFIRMED'),
        ('invoiced', 'INVOICED'),
        ('cancel', 'CANCELLED'),
    ], default='draft', tracking=True)
    name = fields.Char(readonly=True, tracking=True)
    inv_ref = fields.Char(readonly=True, tracking=True, string="Invoice Ref")
    bill_ref = fields.Char(string="Bill Lading Ref", tracking=True)
    date = fields.Date(string="Date", default=datetime.now(),
                       readonly=True, tracking=True, required=True)
    arr_date = fields.Date(string="Arrival Date",
                           default=datetime.now(), tracking=True)
    dep_date = fields.Date(string="Departure Date",
                           default=datetime.now(), tracking=True)
    payment_date = fields.Date(
        string="Departure Date", default=datetime.now(), tracking=True)
    customer_id = fields.Many2one(
        'res.partner', string="Customer", tracking=True)
    journal_id = fields.Many2one(
        'account.journal', string="Journal", required=True)
    return_date = fields.Date(
        string="Container Return Date", default=datetime.now(), tracking=True)
    rela_docs = fields.One2many('open.file.document', 'assoc_file')
    file_lines = fields.One2many('open.file.line', 'assoc_file_line')
    invoice_payment_term_id = fields.Many2one(
        'account.payment.term', required=True)
    account_total = fields.Float(
        string="Total Amount", tracking=True, compute='calculate_account_blc')
    invoice_count = fields.Integer(compute='compute_count')
    company_id = fields.Many2one(
        'res.company', string="Company", default=lambda self: self.env.user.company_id)
    user_id = fields.Many2one(
        "res.users", string="Employee", default=lambda self: self.env.user, readonly=True)

    def create_invoice(self):
        inv_lines = []
        invoice = self.env['account.move'].sudo().create({
            'partner_id': self.customer_id.id,
            'invoice_date': self.date,
            "move_type": "out_invoice",
            'invoice_payment_term_id': self.invoice_payment_term_id.id,
            "journal_id": self.journal_id.id,
            "file_ref": self.name
        })
        if invoice:
            [inv_lines.append((0, 0,
                               {"product_id": x.product_id, "name": x.name, "account_id": x.account_id.id,
                                "quantity": 1,
                                "price_unit": x.amount})) for x in self.file_lines]
            invoice.invoice_line_ids = inv_lines
            self.write({"inv_ref": invoice.name})
        return True


class AccountMove(models.Model):
    _inherit = 'account.move'

    file_ref = fields.Char(
        string="Move Ref", default=datetime.now(), readonly=True, tracking=True)


class OpenFileDocument(models.Model):
    _name = 'open.file.document'
    _description = "The file documents for easy tracking and management"
    _inherit = ["mail.thread", 'mail.activity.mixin']

    date = fields.Date(string="Uploaded On",
                       default=datetime.now(), readonly=True, tracking=True)
    name = fields.Char(string="Document Tittle", tracking=True)
    document = fields.Binary(string="Document")
    assoc_file = fields.Many2one('open.file')
    file_ref = fields.Char(related="assoc_file.name",
                           readonly=True, string="Related File", tracking=True)
    company_id = fields.Many2one(
        'res.company', string="Company", readonly=True)


class OpenFileLine(models.Model):
    _name = 'open.file.line'
    _description = "The Properties of the file for invoice creation"
    _inherit = ["mail.thread", 'mail.activity.mixin']

    @api.onchange("price_unit", "items_qty")
    def _get_total_price(self):
        if self:
            self.amount = self.items_qty*self.price_unit
    product_id = fields.Many2one(
        "product.template", string="Product", tracking=True)
    name = fields.Char(string="Container Number", tracking=True)
    account_id = fields.Many2one(
        'account.account', string="Account", required=True)
    amount = fields.Float(string="Total Price",
                          readonly=True, compute="_get_total_price")
    assoc_file_line = fields.Many2one('open.file', tracking=True)
    company_id = fields.Many2one(
        'res.company', string="Company", readonly=True)
    items_qty = fields.Integer(string="Quantity", default=1)
    price_unit = fields.Float(string="Price")
