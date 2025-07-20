package org.example.controller;

import org.example.model.Company;
import org.example.repository.CompanyRepository;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
public class CompanyController {

    private final CompanyRepository companyRepository;

    public CompanyController(CompanyRepository companyRepository) {
        this.companyRepository = companyRepository;
    }

    // Simple search API: /api/companies/search?query=RyanLBatesDDS
    @GetMapping("/api/companies/search")
    public List<Company> searchCompanies(@RequestParam String query) {
        return companyRepository.findByNamesContainingIgnoreCaseOrEmailContainingIgnoreCase(query, query);
    }
}
